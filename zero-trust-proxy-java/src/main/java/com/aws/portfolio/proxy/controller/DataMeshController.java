package com.aws.portfolio.proxy.controller;

import com.aws.portfolio.proxy.security.JwtAuthenticationFilter;
import com.aws.portfolio.proxy.service.DLPMaskingService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/mesh")
public class DataMeshController {

    private final DLPMaskingService dlpService;

    public DataMeshController(DLPMaskingService dlpService) {
        this.dlpService = dlpService;
    }

    public record QueryRequest(String targetTable, String sqlStatement) {}

    @PostMapping("/query")
    public ResponseEntity<Map<String, Object>> executeFederatedQuery(
            @RequestBody QueryRequest request,
            HttpServletRequest httpRequest) { // Note: We no longer parse headers manually!
        
        // Retrieve the validated role injected by the authentication filter.
        String role = (String) httpRequest.getAttribute(JwtAuthenticationFilter.VALIDATED_ROLE_ATTRIBUTE);

        List<Map<String, Object>> mockDatabaseResponse = List.of(
            Map.of("id", "101", "name", "Alice", "ssn", "123-45-6789", "revenue", 5000.0),
            Map.of("id", "102", "name", "Bob", "ssn", "987-65-4321", "revenue", 300.0)
        );

        List<Map<String, Object>> safeData = dlpService.maskPayload(mockDatabaseResponse, role);

        return ResponseEntity.ok(Map.of(
            "traceId", UUID.randomUUID().toString(),
            "status", "SUCCESS",
            "masked_records", safeData
        ));
    }
}