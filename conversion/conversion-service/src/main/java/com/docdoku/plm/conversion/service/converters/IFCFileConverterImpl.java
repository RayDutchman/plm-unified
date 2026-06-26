

package com.docdoku.plm.conversion.service.converters;

import com.docdoku.plm.server.converters.CADConverter;
import com.docdoku.plm.server.converters.ConversionResultProxy;
import com.docdoku.plm.server.converters.ConverterUtils;


import javax.enterprise.context.ApplicationScoped;
import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Properties;
import java.util.UUID;
import java.util.logging.Level;
import java.util.logging.Logger;

@ApplicationScoped
public class IFCFileConverterImpl implements CADConverter {

    private static final String CONF_PROPERTIES = "/com/docdoku/plm/conversion/service/converters/ifc/conf.properties";
    private static final Properties CONF = new Properties();
    private static final Logger LOGGER = Logger.getLogger(IFCFileConverterImpl.class.getName());

    static {
        try (InputStream inputStream = IFCFileConverterImpl.class.getResourceAsStream(CONF_PROPERTIES)) {
            CONF.load(inputStream);
        } catch (IOException e) {
            LOGGER.log(Level.SEVERE, null, e);
        }
    }

    @Override
    public ConversionResultProxy convert(final URI cadFileUri, final URI tmpDirUri)
            throws ConversionException {
        Path tmpDir = Paths.get(tmpDirUri);
        Path tmpCadFile = Paths.get(cadFileUri);

        String ifcConverter = CONF.getProperty("ifc_convert_path");
        Path executable = Paths.get(ifcConverter);

        // Sanity checks

        if (!Files.exists(executable)) {
            throw new ConversionException(
                    "Cannot convert file \"" + tmpCadFile.toString() + "\", \"" + ifcConverter + "\" is not available");
        }

        if (!Files.isExecutable(executable)) {
            throw new ConversionException("Cannot convert file \"" + tmpCadFile.toString() + "\", \"" + ifcConverter
                    + "\" has no execution rights");
        }

        UUID uuid = UUID.randomUUID();
        // String extension = FileIO.getExtension(cadFile.getName());

        Path convertedFile = tmpDir.resolve(uuid + ".obj");
        Path convertedMtl = tmpDir.resolve(uuid + ".mtl");

        String[] args = {ifcConverter, "--sew-shells", tmpCadFile.toAbsolutePath().toString(),
                convertedFile.toString()};
        ProcessBuilder pb = new ProcessBuilder(args);

        try {
            Process process = pb.start();

            // Read buffers
            String stdOutput = ConverterUtils.inputStreamToString(process.getInputStream());
            String errorOutput = ConverterUtils.inputStreamToString(process.getErrorStream());

            LOGGER.info(stdOutput);

            process.waitFor();

            if (process.exitValue() == 0) {
                List<Path> materials = new ArrayList<>();
                materials.add(convertedMtl);
                return new ConversionResultProxy(convertedFile, materials);
            } else {
                throw new ConversionException(
                        "Cannot convert to obj " + tmpCadFile.toAbsolutePath() + ": " + errorOutput);
            }
        } catch (IOException | InterruptedException e) {
            throw new ConversionException(e);
        }
    }

    @Override
    public boolean canConvertToOBJ(String cadFileExtension) {
        return "ifc".equals(cadFileExtension);
    }

}