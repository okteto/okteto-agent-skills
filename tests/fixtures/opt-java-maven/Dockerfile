# Intentionally un-optimized: unpinned base, COPY . . before dependency resolution.
FROM maven:latest
WORKDIR /app
COPY . .
RUN mvn -q package
CMD ["java", "-jar", "target/catalog-0.1.0.jar"]
