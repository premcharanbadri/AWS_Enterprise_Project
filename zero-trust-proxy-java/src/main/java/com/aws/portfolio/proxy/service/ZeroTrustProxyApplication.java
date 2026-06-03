package com.aws.portfolio.proxy;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Enterprise Application Bootstrap.
 * Initializes the embedded Tomcat server and component scanning.
 */
@SpringBootApplication
public class ZeroTrustProxyApplication {

    public static void main(String[] args) {
        SpringApplication.run(ZeroTrustProxyApplication.class, args);
    }
}