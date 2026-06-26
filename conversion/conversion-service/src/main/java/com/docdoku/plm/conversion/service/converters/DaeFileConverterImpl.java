

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
import java.util.*;
import java.util.logging.Level;
import java.util.logging.Logger;

@ApplicationScoped
public class DaeFileConverterImpl implements CADConverter {

    static final String CONF_PROPERTIES = "/com/docdoku/plm/conversion/service/converters/dae/conf.properties";
    static final Properties CONF = new Properties();
    static final Logger LOGGER = Logger.getLogger(DaeFileConverterImpl.class.getName());

    static {
        try (InputStream inputStream = DaeFileConverterImpl.class.getResourceAsStream(CONF_PROPERTIES)) {
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

        String assimp = CONF.getProperty("assimp");
        Path executable = Paths.get(assimp);

        // Sanity checks

        if (!Files.exists(executable)) {
            throw new ConversionException(
                    "Cannot convert file \"" + tmpCadFile.toString() + "\", \"" + assimp + "\" is not available");
        }

        if (!Files.isExecutable(executable)) {
            throw new ConversionException(
                    "Cannot convert file \"" + tmpCadFile.toString() + "\", \"" + assimp + "\" has no execution rights");
        }

        UUID uuid = UUID.randomUUID();
        Path convertedFile = tmpDir.resolve(uuid + ".obj");
        Path convertedMtlFile = tmpDir.resolve(uuid + ".obj.mtl");

        String[] args = {assimp, "export", tmpCadFile.toAbsolutePath().toString(), convertedFile.toString()};
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
                materials.add(convertedMtlFile);
                return new ConversionResultProxy(convertedFile, materials);
            } else {
                throw new ConversionException(
                        "Cannot convert to obj " + tmpCadFile.toAbsolutePath() + ": " + errorOutput);
            }
        } catch (IOException | InterruptedException e) {
            LOGGER.log(Level.SEVERE, null, e);
            throw new ConversionException(e);
        }
    }

    @Override
    public boolean canConvertToOBJ(String cadFileExtension) {
        return Arrays.asList("dxf", "dae", "lwo", "x", "ac", "cob", "scn", "ms3d").contains(cadFileExtension);
    }

}
