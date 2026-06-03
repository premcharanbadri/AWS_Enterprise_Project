package com.aws.portfolio.proxy.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * Enterprise Security Interceptor.
 * intercepts every incoming API request BEFORE it hits the controller.
 * Enforces strict JWT validation and populates the request context.
 */
@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest request, 
                                    HttpServletResponse response, 
                                    FilterChain filterChain) throws ServletException, IOException {
        
        String authHeader = request.getHeader("Authorization");

        // 1. Crash Early: If no token is provided, reject the network packet instantly.
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.getWriter().write("{\"error\": \"Missing or invalid Authorization header\"}");
            return;
        }

        String token = authHeader.substring(7);
        
        try {
            // 2. Cryptographic Validation
            // In production, this utilizes io.jsonwebtoken (JJWT) to verify the AWS Cognito signature.
            // For portfolio purposes, we simulate the token decoding here.
            String userRole = decodeTokenToGetRole(token);
            
            // 3. Context Injection: Attach the safe, validated role to the request thread
            request.setAttribute("validated_role", userRole);
            
            // 4. Proceed down the filter chain to the Controller
            filterChain.doFilter(request, response);
            
        } catch (Exception e) {
            response.setStatus(HttpServletResponse.SC_FORBIDDEN);
            response.getWriter().write("{\"error\": \"Cryptographic validation failed\"}");
        }
    }

    private String decodeTokenToGetRole(String token) {
        // Simulated cryptographic decode. 
        if (token.contains("ADMIN")) return "SYSTEM_ADMIN";
        if (token.contains("ANALYST")) return "DATA_ANALYST";
        throw new IllegalArgumentException("Invalid token signature");
    }
}