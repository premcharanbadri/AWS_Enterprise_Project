# Stage 1: Build the enterprise application using Maven
FROM maven:3.9.6-eclipse-temurin-21-alpine AS build
WORKDIR /app
# Copy the POM and source code (Assuming you have a standard pom.xml)
COPY pom.xml .
COPY src ./src
# Compile the Java application, skipping tests to speed up the Docker build
RUN mvn clean package -DskipTests

# Stage 2: Create the lightweight, secure production image
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app

# Security Best Practice: Do not run containers as root
RUN addgroup -S spring && adduser -S spring -G spring
USER spring:spring

# Copy the compiled JAR from the build stage
COPY --from=build /app/target/*.jar app.jar

# Expose standard web traffic port
EXPOSE 8080

# Execute the application
ENTRYPOINT ["java", "-jar", "/app/app.jar"]