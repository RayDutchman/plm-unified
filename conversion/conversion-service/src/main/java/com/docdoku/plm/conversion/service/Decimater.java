package com.docdoku.plm.conversion.service;

import com.docdoku.plm.server.converters.ConverterUtils;

import javax.inject.Inject;
import javax.inject.Singleton;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;

@Singleton
class Decimater {

    @Inject
    private ConversionServiceConfig conversionServiceConfig;

    private static Logger LOGGER = Logger.getLogger(Decimater.class.getName());

    private static final float[] RATIO = new float[]{1f, 0.6f, 0.2f};

    Map<Integer, Path> decimate(Path file, Path tempDir) {

        Map<Integer,Path> lods = new HashMap<>();

        LOGGER.log(Level.INFO, "Decimate file in progress");

        // sanity checks
        String decimater = conversionServiceConfig.getDecimaterPath();
        Path executable = Paths.get(decimater);
        if (!executable.toFile().exists()) {
            LOGGER.log(Level.WARNING, "Cannot decimate file \"{0}\", decimater \"{1}\" is not available",
                    new Object[]{file.getFileName(), decimater});
            return lods;
        }
        if (!Files.isExecutable(executable)) {
            LOGGER.log(Level.WARNING, "Cannot decimate file \"{0}\", decimater \"{1}\" has no execution rights",
                    new Object[]{file.getFileName(), decimater});
            return lods;
        }

        try {
            String[] args = {decimater, "-i", file.toAbsolutePath().toString(), "-o",
                    tempDir.toAbsolutePath().toString(), String.valueOf(RATIO[0]), String.valueOf(RATIO[1]),
                    String.valueOf(RATIO[2])};

            LOGGER.log(Level.INFO, "Decimate command\n{0}", args);

            // Add redirectErrorStream, fix process hang up
            ProcessBuilder pb = new ProcessBuilder(args).redirectErrorStream(true);

            Process proc = pb.start();

            String stdOutput = ConverterUtils.inputStreamToString(proc.getInputStream());

            proc.waitFor();

            if (proc.exitValue() == 0) {
                LOGGER.log(Level.INFO, "Decimation done");

                String fileName = file.getFileName().toString();

                for (int i = 0; i < RATIO.length; i++) {
                    Path lod = tempDir.resolve(fileName.replaceAll("\\.obj$", Math.round((RATIO[i] * 100)) + ".obj"));
                    Path lodRelative = Paths.get(tempDir.getFileName() + "/" + lod.getFileName().toString());
                    if(Files.exists(lodRelative)) {
                        lods.put(i, lodRelative);
                    }
                }

            } else {
                LOGGER.log(Level.SEVERE, "Decimation failed with code = {0} {1}", new Object[]{proc.exitValue(), stdOutput});
            }

        } catch (IOException | InterruptedException e) {
            LOGGER.log(Level.SEVERE, "Decimation failed for " + file.toAbsolutePath(), e);
        }

        return lods;
    }

}
