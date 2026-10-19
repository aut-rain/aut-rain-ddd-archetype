#set( $dollar = '$' )
#set( $hash = '#' )
${hash}!/usr/bin/env bash
${hash} Sourced by the official MySQL entrypoint on an EMPTY data volume only.
${hash} Validate before interpolating credentials into SQL.
for key in NACOS_DB_PASSWORD XXL_JOB_DB_PASSWORD XXL_JOB_ADMIN_PASSWORD; do
  value="${dollar}{!key}"
  if [[ ! "${dollar}value" =~ ^[A-Za-z0-9_-]{24,128}${dollar} ]]; then
    echo "Invalid middleware credential: ${dollar}key" >&2
    exit 1
  fi
done
docker_process_sql <<EOSQL
CREATE DATABASE IF NOT EXISTS nacos_config CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
CREATE DATABASE IF NOT EXISTS xxl_job CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'nacos'@'%' IDENTIFIED BY '${dollar}NACOS_DB_PASSWORD';
CREATE USER 'xxl_job'@'%' IDENTIFIED BY '${dollar}XXL_JOB_DB_PASSWORD';
GRANT ALL ON nacos_config.* TO 'nacos'@'%';
GRANT ALL ON xxl_job.* TO 'xxl_job'@'%';
USE nacos_config;
SOURCE /opt/middleware-sql/nacos.sql;
USE xxl_job;
SOURCE /opt/middleware-sql/xxl-job.sql;
INSERT INTO xxl_job_user (username, password, role, permission)
VALUES ('admin', MD5('${dollar}XXL_JOB_ADMIN_PASSWORD'), 1, NULL);
EOSQL
