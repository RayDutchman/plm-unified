package com.docdoku.plm.conversion.service;


import com.docdoku.plm.api.DocDokuPLMClientFactory;
import com.docdoku.plm.api.client.ApiClient;
import com.docdoku.plm.api.client.ApiException;
import com.docdoku.plm.api.models.ConversionResultDTO;
import com.docdoku.plm.api.services.PartApi;
import io.quarkus.runtime.ShutdownEvent;
import io.quarkus.runtime.StartupEvent;
import org.dozer.DozerBeanMapperSingletonWrapper;
import org.dozer.Mapper;
import org.eclipse.microprofile.reactive.messaging.Incoming;
import com.docdoku.plm.server.core.common.BinaryResource;
import com.docdoku.plm.server.core.exceptions.FileNotFoundException;
import com.docdoku.plm.server.core.exceptions.StorageException;
import com.docdoku.plm.server.core.product.PartIterationKey;
import com.docdoku.plm.server.core.util.FileIO;
import com.docdoku.plm.server.core.util.Tools;
import com.docdoku.plm.server.converters.CADConverter;
import com.docdoku.plm.server.converters.ConversionOrder;
import com.docdoku.plm.server.converters.ConversionResultProxy;

import javax.annotation.PostConstruct;
import javax.enterprise.context.ApplicationScoped;
import javax.enterprise.event.Observes;
import javax.enterprise.inject.Any;
import javax.enterprise.inject.Instance;
import javax.inject.Inject;
import java.io.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;
import java.util.UUID;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * @author Morgan Guimard
 */
@ApplicationScoped
public class App {

    @Inject
    ConversionServiceConfig conversionServiceConfig;

    @Inject
    @Any
    Instance<CADConverter> converters;

    @Inject
    GeometryParser geometryParser;

    @Inject
    Decimater decimater;

    private static Logger LOGGER = Logger.getLogger(App.class.getName());
    private final static Mapper MAPPER = DozerBeanMapperSingletonWrapper.getInstance();

    void onStart(@Observes StartupEvent ev) {
        LOGGER.info("The application is starting nicely...");
    }

    void onStop(@Observes ShutdownEvent ev) {
        LOGGER.info("The application is stopping...");
    }

    @PostConstruct
    void init(){
        LOGGER.info("Stating QueueListener initialized");
    }

    @Incoming("conversion_orders")
    public void onConversionOrder(ConversionOrder conversionOrder){

        PartIterationKey partIterationKey = conversionOrder.getPartIterationKey();

        LOGGER.info("Got conversion order for " + partIterationKey);

        BinaryResource cadBinaryResource = conversionOrder.getBinaryResource();
        String ext = FileIO.getExtension(cadBinaryResource.getName());
        CADConverter converter = selectConverter(ext);

        String userToken = conversionOrder.getUserToken();

        if (null == converter) {
            LOGGER.log(Level.WARNING,"No CAD converter able to handle " + cadBinaryResource.getName());
            return;
        }

        Path tempDir;
        UUID uuid = UUID.randomUUID();
        UUID tempFileUUID = UUID.randomUUID();

        try {
            tempDir = Files.createDirectory(Paths.get(conversionServiceConfig.getConversionsPath() + "/" + uuid));
            LOGGER.info("Using temp dir: " + tempDir );
        } catch (IOException e) {
            LOGGER.log(Level.SEVERE,null,e);
            sendError(userToken, partIterationKey, e.getMessage());
            return;
        }

        try (InputStream in = getBinaryResourceInputStream(cadBinaryResource)) {

            Path tmpCadFile = Paths.get(tempDir.toAbsolutePath() + "/" + tempFileUUID + "." + ext);
            Files.copy(in, tmpCadFile);

            try (ConversionResultProxy conversionResult = converter.convert(tmpCadFile.toUri(), tempDir.toUri())) {
                LOGGER.info("Conversion ended for " + partIterationKey);

                conversionResult.setTempDir(tempDir);

                if(null != conversionResult.getStdOutput()){
                    LOGGER.warning("Conversion has errors \n "+ conversionResult.getErrorOutput());
                }else {
                    LOGGER.info("Conversions ended without errors");
                }

                Path convertedFile = conversionResult.getConvertedFile();

                if(null != convertedFile){
                    double[] box = geometryParser.calculateBox(convertedFile);
                    conversionResult.setBox(box);

                    Map<Integer, Path> lods = decimater.decimate(convertedFile, tempDir);
                    // Keep only converted file if lods generation failed
                    if(lods.isEmpty()){
                        lods.put(0, Paths.get(convertedFile.getFileName().toString()));
                    }

                    conversionResult.setConvertedFileLODs(lods);
                }

                ConversionResultDTO conversionResultDTO = MAPPER.map(conversionResult,ConversionResultDTO.class);
                sendResult(userToken, partIterationKey, conversionResultDTO);

            } catch (Exception e) {
                LOGGER.log(Level.SEVERE,null,e);
                sendError(userToken, partIterationKey, e.getMessage());
            }

        } catch (FileNotFoundException | StorageException | IOException e) {
            sendError(userToken, partIterationKey, e.getMessage());
        }

    }

    private CADConverter selectConverter(String ext) {
        for (CADConverter converter : converters) {
            try {
                if (converter.canConvertToOBJ(ext)) {
                    return converter;
                }
            } catch (Exception e) {
                LOGGER.log(Level.SEVERE, "Something gone wrong with converter instantiation " + converter, e);
            }
        }
        return null;
    }


    private InputStream getBinaryResourceInputStream(BinaryResource pBinaryResource) throws StorageException, FileNotFoundException {
        File file = new File(getVirtualPath(pBinaryResource));
        return getInputStream(file);
    }

    private String getVirtualPath(BinaryResource pBinaryResource) {
        String normalizedName = Tools.unAccent(pBinaryResource.getFullName());
        return conversionServiceConfig.getVaultPath() + "/" + normalizedName;
    }

    private InputStream getInputStream(File file) throws StorageException, FileNotFoundException {
        if (file.exists()) {
            try {
                return new BufferedInputStream(new FileInputStream(file));
            } catch (java.io.FileNotFoundException e) {
                throw new StorageException(e.getMessage(), e);
            }
        } else {
            throw new FileNotFoundException(file.getAbsolutePath() + " not found");
        }
    }

    private void sendError(String userToken, PartIterationKey partIterationKey, String message) {
        LOGGER.severe("Conversion error:\n" + message);
        ConversionResultDTO conversionResult = new ConversionResultDTO();
        conversionResult.setErrorOutput(message);
        sendResult(userToken, partIterationKey, conversionResult);
    }

    private void sendResult(String userToken, PartIterationKey partIterationKey, ConversionResultDTO conversionResult) {
        String host = conversionServiceConfig.getHost();
        ApiClient client = DocDokuPLMClientFactory.createJWTClient(host, userToken);
        PartApi partApi = new PartApi(client);
        String workspaceId = partIterationKey.getWorkspaceId();
        String partNumber = partIterationKey.getPartMasterNumber();
        String partVersion = partIterationKey.getPartRevisionVersion();
        try {
            partApi.sendConversionResult(workspaceId, partNumber, partVersion, conversionResult);
            LOGGER.info("Conversion callback success");
        } catch (ApiException e) {
            LOGGER.severe("Conversion callback error");
        }
    }

}
