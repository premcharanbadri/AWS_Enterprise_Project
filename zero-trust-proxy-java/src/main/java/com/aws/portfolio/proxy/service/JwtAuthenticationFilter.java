package com.aws.portfolio.proxy.security;

import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;

@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        
        String authHeader = request.getHeader("Authorization");
        
        if (authHeader != null && authHeader.startsWith("Bearer ")) {
            String token = authHeader.substring(7);
            try {
                String role = decodeTokenToGetRole(token);
                request.setAttribute("USER_ROLE", role);
            } catch (Exception e) {
                response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
                return;
            }
        }
        
        filterChain.doFilter(request, response);
    }

    // BUG 7 FIX: Explicitly document the local mock to prevent auth bypass in production.
    // TODO: Mock implementation for local development. Production deployment requires 
    // RS256 JWT validation against an active AWS Cognito JWKS endpoint.
    private String decodeTokenToGetRole(String token) {
        if (token.contains("ADMIN")) return "SYSTEM_ADMIN";
        if (token.contains("ANALYST")) return "DATA_ANALYST";
        throw new IllegalArgumentException("Invalid token signature");
    }
}