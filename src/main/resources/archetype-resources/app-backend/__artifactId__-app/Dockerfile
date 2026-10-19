#set( $dollar = '$' )
#set( $hash = '#' )
FROM eclipse-temurin:21-jre-jammy
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 appuser && useradd --uid 10001 --gid appuser --no-create-home appuser
WORKDIR /app
ARG JAR_FILE=target/${artifactId}-app.jar
COPY --chown=10001:10001 ${dollar}{JAR_FILE} /app/app.jar
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]

