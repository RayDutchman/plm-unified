
package com.docdoku.plm.conversion.service.converters;


import com.docdoku.plm.server.converters.CADConverter;
import com.docdoku.plm.server.converters.ConversionResultProxy;

import javax.enterprise.context.ApplicationScoped;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;
import java.util.Properties;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.logging.Level;
import java.util.logging.Logger;

@ApplicationScoped
public class StepFileConverterImpl implements CADConverter {

    private static final Logger LOGGER = Logger.getLogger(StepFileConverterImpl.class.getName());
    private static final String CONF_PROPERTIES = "/com/docdoku/plm/conversion/service/converters/step/conf.properties";
    private static final String PYTHON_SCRIPT    = "/com/docdoku/plm/conversion/service/converters/step/convert_step_glb.py";
    private static final Properties CONF = new Properties();

    // P3.1：LOD 后缀与索引的映射（与 convert_step_glb.py 约定一致）
    private static final int[] LOD_SUFFIXES = {100, 60, 20};

    static {
        try (InputStream inputStream = StepFileConverterImpl.class.getResourceAsStream(CONF_PROPERTIES)) {
            if (inputStream == null) {
                LOGGER.severe("conf.properties not found on classpath: " + CONF_PROPERTIES);
            } else {
                CONF.load(inputStream);
            }
        } catch (IOException e) {
            LOGGER.log(Level.SEVERE, "Failed to load conf.properties", e);
        }
    }

    @Override
    public ConversionResultProxy convert(final URI cadFileUri, final URI tmpDirUri)
            throws ConversionException {

        String pythonInterpreter = CONF.getProperty("pythonInterpreter");
        String freeCadLibPath    = CONF.getProperty("freeCadLibPath", "");

        if (pythonInterpreter == null || pythonInterpreter.trim().isEmpty()) {
            throw new ConversionException(
                "pythonInterpreter not configured in conf.properties — check " + CONF_PROPERTIES);
        }

        Path tmpDir     = Paths.get(tmpDirUri);
        Path tmpCadFile = Paths.get(cadFileUri);

        UUID uuid       = UUID.randomUUID();
        // P3.1：--lod 模式下 Python 脚本会生成 {uuid}100.glb/{uuid}60.glb/{uuid}20.glb，
        // 单精度模式则生成 {uuid}.glb，outputFile 参数作为 stem 使用
        Path tmpGLBStem = tmpDir.resolve(uuid.toString());
        Path tmpGLBFile = tmpDir.resolve(uuid + ".glb");

        Path scriptPath = tmpDir.resolve("convert_script_" + uuid + ".py");
        try (InputStream scriptStream = StepFileConverterImpl.class.getResourceAsStream(PYTHON_SCRIPT)) {
            if (scriptStream == null) {
                throw new ConversionException("Python script resource not found: " + PYTHON_SCRIPT);
            }
            Files.copy(scriptStream, scriptPath);
        } catch (IOException e) {
            throw new ConversionException("Unable to copy python script", e);
        }

        // P3.1：传入 --lod 参数，输出三个精度文件；-o 传 stem（不含后缀）
        String[] args = {
            pythonInterpreter,
            scriptPath.toAbsolutePath().toString(),
            "-l", freeCadLibPath,
            "-i", tmpCadFile.toAbsolutePath().toString(),
            "-o", tmpGLBStem.toAbsolutePath().toString(),
            "--lod"
        };
        ProcessBuilder pb = new ProcessBuilder(args);

        try {
            Process process = pb.start();

            ExecutorService pool = Executors.newFixedThreadPool(2);
            Future<String> stdFuture = pool.submit(() -> drainStream(process.getInputStream()));
            Future<String> errFuture = pool.submit(() -> drainStream(process.getErrorStream()));
            pool.shutdown();

            process.waitFor();

            String stdOutput   = stdFuture.get();
            String errorOutput = errFuture.get();

            if (stdOutput != null && !stdOutput.isEmpty()) {
                LOGGER.info(stdOutput);
            }

            if (process.exitValue() == 0) {
                // P3.1：收集三个 LOD 文件，写入 convertedFileLODs
                // LOD0(100%)=quality 0, LOD1(60%)=quality 1, LOD2(20%)=quality 2
                Map<Integer, Path> lods = new HashMap<>();
                for (int i = 0; i < LOD_SUFFIXES.length; i++) {
                    Path lodPath = tmpDir.resolve(uuid + LOD_SUFFIXES[i] + ".glb");
                    if (Files.exists(lodPath)) {
                        lods.put(i, lodPath);
                        LOGGER.info("LOD" + i + " file: " + lodPath.getFileName());
                    } else {
                        LOGGER.warning("LOD" + i + " file not found: " + lodPath.getFileName());
                    }
                }

                if (!lods.isEmpty()) {
                    // 以 LOD0（最高精度）作为 convertedFile（兼容旧回调路径）
                    Path lod0 = lods.get(0);
                    if (lod0 == null) lod0 = lods.values().iterator().next();
                    ConversionResultProxy result = new ConversionResultProxy(lod0);
                    result.setConvertedFileLODs(lods);
                    return result;
                } else {
                    // fallback：无 LOD 文件（不应发生），尝试单文件
                    if (Files.exists(tmpGLBFile)) {
                        return new ConversionResultProxy(tmpGLBFile);
                    }
                    throw new ConversionException(
                        "Cannot convert to GLB (--lod mode): no output files found for " + tmpCadFile.toAbsolutePath());
                }
            } else {
                throw new ConversionException(
                    "Cannot convert to GLB: " + tmpCadFile.toAbsolutePath() + ": " + errorOutput);
            }
        } catch (IOException e) {
            LOGGER.log(Level.SEVERE, "Process I/O error during GLB conversion", e);
            throw new ConversionException(e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new ConversionException(e);
        } catch (java.util.concurrent.ExecutionException e) {
            throw new ConversionException("Failed to read process output", e);
        }
    }

    /** Drain an InputStream into a String, ignoring errors silently. */
    private static String drainStream(InputStream is) {
        StringBuilder sb = new StringBuilder();
        try (BufferedReader br = new BufferedReader(new InputStreamReader(is))) {
            String line;
            while ((line = br.readLine()) != null) {
                sb.append(line).append('\n');
            }
        } catch (IOException e) {
            // Stream already closed — ignore
        }
        return sb.toString();
    }

    @Override
    public boolean canConvertToOBJ(String cadFileExtension) {
        // Method name is a misnomer (legacy interface); output is now GLB.
        return Arrays.asList("stp", "step", "igs", "iges").contains(cadFileExtension);
    }

}
