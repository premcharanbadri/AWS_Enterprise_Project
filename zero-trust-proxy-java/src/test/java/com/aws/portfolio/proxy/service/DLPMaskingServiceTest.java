package com.aws.portfolio.proxy.service;

import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.assertEquals;

class DLPMaskingServiceTest {

    private final DLPMaskingService dlpService = new DLPMaskingService();

    @Test
    void testDataAnalystReceivesMaskedSSN() {
        List<Map<String, Object>> input = List.of(
            Map.of("name", "Alice", "ssn", "123-45-6789", "cc", "4111-2222-3333-4444")
        );

        List<Map<String, Object>> result = dlpService.maskPayload(input, "DATA_ANALYST");

        // Assert data is masked correctly
        assertEquals("***-**-****", result.get(0).get("ssn"));
        assertEquals("****-****-****-XXXX", result.get(0).get("cc"));
        
        assertEquals("Alice", result.get(0).get("name")); // Non-PII is left alone
    }

    @Test
    void testSystemAdminReceivesRawData() {
        List<Map<String, Object>> input = List.of(
            Map.of("name", "Alice", "ssn", "123-45-6789")
        );

        List<Map<String, Object>> result = dlpService.maskPayload(input, "SYSTEM_ADMIN");

        // Assert Admin gets the exact raw data
        assertEquals("123-45-6789", result.get(0).get("ssn"));
    }
}