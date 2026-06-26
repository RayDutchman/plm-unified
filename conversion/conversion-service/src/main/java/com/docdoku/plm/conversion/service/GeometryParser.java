package com.docdoku.plm.conversion.service;

import javax.inject.Singleton;
import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Singleton
public class GeometryParser {

    private static final Logger LOGGER = Logger.getLogger(GeometryParser.class.getName());

    public GeometryParser() {
    }

    /**
     * Computes the bounding box of a 3D geometry file.
     * Supports OBJ (text) and GLB (binary glTF 2.0).
     *
     * @param path path to resource
     * @return double[6]: {xMin, yMin, zMin, xMax, yMax, zMax}
     */
    public double[] calculateBox(Path path) {
        String fileName = path.getFileName().toString().toLowerCase();
        if (fileName.endsWith(".glb")) {
            return calculateBoxFromGlb(path);
        } else {
            return calculateBoxFromObj(path);
        }
    }

    /**
     * Parse bounding box from OBJ text file by scanning vertex lines.
     */
    private double[] calculateBoxFromObj(Path path) {
        boolean init = false;
        double xMin = 0, xMax = 0, yMin = 0, yMax = 0, zMin = 0, zMax = 0;

        try (BufferedReader br = new BufferedReader(new FileReader(path.toFile()))) {
            String line;
            while ((line = br.readLine()) != null) {
                if (line.startsWith("v ") || line.startsWith("v  ")) {
                    // Handle both "v x y z" and "v  x y z" formats
                    String trimmed = line.substring(1).trim();
                    String[] parts = trimmed.split("\\s+");
                    if (parts.length >= 3) {
                        double x = Double.parseDouble(parts[0]);
                        double y = Double.parseDouble(parts[1]);
                        double z = Double.parseDouble(parts[2]);
                        if (!init) {
                            xMin = xMax = x;
                            yMin = yMax = y;
                            zMin = zMax = z;
                            init = true;
                        } else {
                            xMin = Math.min(x, xMin); xMax = Math.max(x, xMax);
                            yMin = Math.min(y, yMin); yMax = Math.max(y, yMax);
                            zMin = Math.min(z, zMin); zMax = Math.max(z, zMax);
                        }
                    }
                }
            }
        } catch (IOException e) {
            LOGGER.log(Level.SEVERE, "Cannot parse vertices from obj", e);
        } catch (NumberFormatException e) {
            LOGGER.log(Level.SEVERE, "Cannot parse double value from obj", e);
        }

        return new double[]{xMin, yMin, zMin, xMax, yMax, zMax};
    }

    /**
     * Parse bounding box from GLB (binary glTF 2.0) file.
     *
     * GLB layout:
     *   12 bytes header  (magic 0x46546C67, version, totalLength)
     *   Chunk 0: JSON  (chunkLength, chunkType 0x4E4F534A, chunkData)
     *   Chunk 1: BIN   (chunkLength, chunkType 0x004E4942, chunkData)
     *
     * The JSON chunk contains the glTF asset definition.
     * Each POSITION accessor has "min" and "max" arrays [x, y, z].
     * We aggregate across all accessors to get the global bounding box.
     */
    private double[] calculateBoxFromGlb(Path path) {
        double xMin = 0, xMax = 0, yMin = 0, yMax = 0, zMin = 0, zMax = 0;
        boolean init = false;

        try (RandomAccessFile raf = new RandomAccessFile(path.toFile(), "r")) {

            // Read GLB header
            byte[] header = new byte[12];
            raf.readFully(header);
            ByteBuffer hdr = ByteBuffer.wrap(header).order(ByteOrder.LITTLE_ENDIAN);
            int magic = hdr.getInt();
            // 0x46546C67 = "glTF"
            if (magic != 0x46546C67) {
                LOGGER.warning("Not a valid GLB file: " + path);
                return new double[]{0, 0, 0, 0, 0, 0};
            }
            // int version = hdr.getInt(); // skip
            // int totalLen = hdr.getInt(); // skip

            // Read chunk 0 (JSON)
            byte[] chunkHeader = new byte[8];
            raf.readFully(chunkHeader);
            ByteBuffer ch = ByteBuffer.wrap(chunkHeader).order(ByteOrder.LITTLE_ENDIAN);
            int chunkLength = ch.getInt();
            int chunkType   = ch.getInt();

            // chunkType 0x4E4F534A = "JSON"
            if (chunkType != 0x4E4F534A) {
                LOGGER.warning("First GLB chunk is not JSON: " + path);
                return new double[]{0, 0, 0, 0, 0, 0};
            }

            byte[] jsonBytes = new byte[chunkLength];
            raf.readFully(jsonBytes);
            String json = new String(jsonBytes, StandardCharsets.UTF_8);

            double[] globalMin = extractGlobalPositionBound(json, true);
            double[] globalMax = extractGlobalPositionBound(json, false);

            if (globalMin != null && globalMax != null) {
                xMin = globalMin[0]; yMin = globalMin[1]; zMin = globalMin[2];
                xMax = globalMax[0]; yMax = globalMax[1]; zMax = globalMax[2];
                init = true;
            }

        } catch (IOException e) {
            LOGGER.log(Level.SEVERE, "Cannot parse GLB bounding box from: " + path, e);
        }

        if (!init) {
            LOGGER.warning("Could not extract bounding box from GLB: " + path + " — using zeros");
        }

        return new double[]{xMin, yMin, zMin, xMax, yMax, zMax};
    }

    /**
     * Extract the global min or max vec3 values from a glTF JSON string
     * by finding all "min":[...] or "max":[...] entries in accessor objects
     * and computing the overall min/max across all of them.
     *
     * @param json     glTF JSON content
     * @param key      "min" or "max"
     * @return double[3] global {x, y, z}, or null if not found
     */
    private double[] extractGlobalPositionBound(String json, boolean useMin) {
        List<String> accessors = extractTopLevelObjects(json, "accessors");
        if (accessors.isEmpty()) {
            return null;
        }

        Set<Integer> positionAccessorIndexes = extractPositionAccessorIndexes(json);
        if (positionAccessorIndexes.isEmpty()) {
            return null;
        }

        double rx = useMin ? Double.MAX_VALUE : -Double.MAX_VALUE;
        double ry = useMin ? Double.MAX_VALUE : -Double.MAX_VALUE;
        double rz = useMin ? Double.MAX_VALUE : -Double.MAX_VALUE;
        boolean found = false;

        for (Integer accessorIndex : positionAccessorIndexes) {
            if (accessorIndex < 0 || accessorIndex >= accessors.size()) {
                continue;
            }
            double[] values = extractAccessorBound(accessors.get(accessorIndex), useMin ? "min" : "max");
            if (values == null) {
                continue;
            }
            if (useMin) {
                rx = Math.min(rx, values[0]);
                ry = Math.min(ry, values[1]);
                rz = Math.min(rz, values[2]);
            } else {
                rx = Math.max(rx, values[0]);
                ry = Math.max(ry, values[1]);
                rz = Math.max(rz, values[2]);
            }
            found = true;
        }

        return found ? new double[]{rx, ry, rz} : null;
    }

    private Set<Integer> extractPositionAccessorIndexes(String json) {
        Set<Integer> indexes = new HashSet<>();
        Pattern pattern = Pattern.compile("\\\"POSITION\\\"\\s*:\\s*(\\d+)");
        Matcher matcher = pattern.matcher(json);
        while (matcher.find()) {
            indexes.add(Integer.parseInt(matcher.group(1)));
        }
        return indexes;
    }

    private double[] extractAccessorBound(String accessorJson, String key) {
        Pattern pattern = Pattern.compile("\\\"" + key + "\\\"\\s*:\\s*\\[\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)\\s*,\\s*([-+0-9.eE]+)");
        Matcher matcher = pattern.matcher(accessorJson);
        if (!matcher.find()) {
            return null;
        }
        try {
            return new double[]{
                Double.parseDouble(matcher.group(1)),
                Double.parseDouble(matcher.group(2)),
                Double.parseDouble(matcher.group(3))
            };
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private List<String> extractTopLevelObjects(String json, String arrayKey) {
        List<String> objects = new ArrayList<>();
        int keyIndex = json.indexOf("\"" + arrayKey + "\"");
        if (keyIndex < 0) {
            return objects;
        }
        int arrayStart = json.indexOf('[', keyIndex);
        if (arrayStart < 0) {
            return objects;
        }
        int arrayEnd = findMatchingBracket(json, arrayStart, '[', ']');
        if (arrayEnd < 0) {
            return objects;
        }

        int index = arrayStart + 1;
        while (index < arrayEnd) {
            char current = json.charAt(index);
            if (current == '{') {
                int objectEnd = findMatchingBracket(json, index, '{', '}');
                if (objectEnd < 0) {
                    break;
                }
                objects.add(json.substring(index, objectEnd + 1));
                index = objectEnd + 1;
            } else {
                index++;
            }
        }
        return objects;
    }

    private int findMatchingBracket(String text, int start, char open, char close) {
        int depth = 0;
        boolean inString = false;
        boolean escaped = false;
        for (int i = start; i < text.length(); i++) {
            char ch = text.charAt(i);
            if (escaped) {
                escaped = false;
                continue;
            }
            if (ch == '\\') {
                escaped = true;
                continue;
            }
            if (ch == '"') {
                inString = !inString;
                continue;
            }
            if (inString) {
                continue;
            }
            if (ch == open) {
                depth++;
            } else if (ch == close) {
                depth--;
                if (depth == 0) {
                    return i;
                }
            }
        }
        return -1;
    }

}
