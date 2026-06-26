/*******************************************************************************
  * Copyright (c) 2017-2019 DocDoku.
  * All rights reserved. This program and the accompanying materials
  * are made available under the terms of the Eclipse Public License v1.0
  * which accompanies this distribution, and is available at
  * http://www.eclipse.org/legal/epl-v10.html
  *
  * Contributors:
  *    DocDoku - initial API and implementation
  *******************************************************************************/

package com.docdoku.plm.conversion.service;

import com.docdoku.plm.api.models.ConversionResultDTO;
import com.docdoku.plm.api.models.PositionDTO;
import org.dozer.DozerConverter;
import com.docdoku.plm.server.core.product.ConversionResult;
import com.docdoku.plm.server.converters.ConversionResultProxy;

import java.nio.file.Path;
import java.util.*;
import java.util.stream.Collectors;

/**
 * @author Morgan Guimard
 */
public class ConversionResultDozerConverter extends DozerConverter<ConversionResultProxy, ConversionResultDTO> {

    public ConversionResultDozerConverter() {
        super(ConversionResultProxy.class, ConversionResultDTO.class);
    }

    @Override
    public ConversionResultDTO convertTo(ConversionResultProxy conversionResult, ConversionResultDTO pConversionResultDTO) {
        ConversionResultDTO conversionResultDTO = new ConversionResultDTO();

        conversionResultDTO.setErrorOutput(conversionResult.getErrorOutput());
        conversionResultDTO.setStdOutput(conversionResult.getStdOutput());

        // dir name only
        conversionResultDTO.setTempDir(conversionResult.getTempDir().getFileName().toString());

        if(conversionResult.getBox() != null) {
            conversionResultDTO.setBox(Arrays.stream(conversionResult.getBox())
                    .map(Double::new).boxed().collect(Collectors.toList()));
        }

        if(conversionResult.getConvertedFile() != null) {
            // file name only
            conversionResultDTO.setConvertedFile(conversionResult.getConvertedFile().getFileName().toString());
        }

        if(conversionResult.getConvertedFileLODs() != null) {
            Map<String,String> lods = new HashMap<>();
            // file names only
            conversionResult.getConvertedFileLODs().forEach((key, value) -> lods.put(String.valueOf(key), value.getFileName().toString()));
            conversionResultDTO.setConvertedFileLODs(lods);
        }

        if(conversionResult.getMaterials() != null) {
            // file names only
            List<String> mat = conversionResult.getMaterials().stream().map(m -> m.getFileName().toString()).collect(Collectors.toList());
            conversionResultDTO.setMaterials(mat);
        }

        if(conversionResult.getComponentPositionMap() != null) {
            Map<String, List<PositionDTO>> positions = new HashMap<>();
            conversionResult.getComponentPositionMap().forEach((key, value) -> {
                positions.put(key, transformPositionListToPositionDTOList(value));
            });
            conversionResultDTO.setComponentPositionMap(positions);
        }

        return conversionResultDTO;
    }

    @Override
    public ConversionResultProxy convertFrom(ConversionResultDTO conversionResultDTO, ConversionResultProxy pConversionResult) {
        return pConversionResult;
    }

    private static List<PositionDTO> transformPositionListToPositionDTOList(List<ConversionResult.Position> positions){
        return  positions.stream().map(p -> {
            PositionDTO positionDTO = new PositionDTO();
            positionDTO.setRotationmatrix(transformPrimitiveToObject(p.getRotationMatrix()));
            positionDTO.setTranslation(transformPrimitiveToObject(p.getTranslation()));
            return positionDTO;
        }).collect(Collectors.toList());
    }

    private static List<Double> transformPrimitiveToObject(double[] arr){
        return Arrays.stream(arr)
                .map(Double::new).boxed().collect(Collectors.toList());
    }
    private static List<List<Double>> transformPrimitiveToObject(double[][] arr) {
        return Arrays.stream(arr)
                        .map(ConversionResultDozerConverter::transformPrimitiveToObject)
                        .collect(Collectors.toList());
    }
}
