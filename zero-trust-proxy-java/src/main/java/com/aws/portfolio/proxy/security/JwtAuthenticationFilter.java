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

    // Shared with the controller so the validated identity is read back under the
    // same key the filter writes it to.
    public static final String VALIDATED_ROLE_ATTRIBUTE = "validated_role";

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {

        String authHeader = request.getHeader("Authorization");

        // Zero-trust default-deny: a request without a Bearer token never reaches
        // the business logic.
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            return;
        }

        String token = authHeader.substring(7);
        String role;
        try {
            role = decodeTokenToGetRole(token);
        } catch (Exception e) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            return;
        }

        request.setAttribute(VALIDATED_ROLE_ATTRIBUTE, role);
        filterChain.doFilter(request, response);
    }

    // TODO: Mock implementation for local development only. Production deployment
    // requires RS256 JWT signature validation against an active AWS Cognito JWKS
    // endpoint (e.g. spring-boot-starter-oauth2-resource-server).
    private String decodeTokenToGetRole(String token) {
        if (token.contains("ADMIN")) return "SYSTEM_ADMIN";
        if (token.contains("ANALYST")) return "DATA_ANALYST";
        throw new IllegalArgumentException("Invalid token signature");
    }
}
