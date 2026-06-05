package com.aws.portfolio.proxy.service;

import org.springframework.stereotype.Service;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

@Service
public class DLPMaskingService {

    private static final Pattern SSN_PATTERN = Pattern.compile("\\b\\d{3}-\\d{2}-\\d{4}\\b");
    private static final Pattern CC_PATTERN = Pattern.compile("\\b\\d{4}[- ]\\d{4}[- ]\\d{4}[- ]\\d{1,4}\\b");

    public List<Map<String, Object>> maskPayload(List<Map<String, Object>> rawData, String userRole) {
        if ("SYSTEM_ADMIN".equalsIgnoreCase(userRole)) {
            return rawData; 
        }
        return rawData.stream().map(this::maskRecord).collect(Collectors.toList());
    }

    private Map<String, Object> maskRecord(Map<String, Object> record) {
        return record.entrySet().stream()
            .collect(Collectors.toMap(
                Map.Entry::getKey,
                entry -> maskValue(entry.getValue())
            ));
    }

    private Object maskValue(Object value) {
        if (!(value instanceof String)) return value;
        
        String strVal = (String) value;
        strVal = SSN_PATTERN.matcher(strVal).replaceAll("***-**-****");
        strVal = CC_PATTERN.matcher(strVal).replaceAll("****-****-****-XXXX");
        
        return strVal;
    }
}
