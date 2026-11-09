#set( $dollar = '$' )
#set( $hash = '#' )
/*
 * description: 提供基础 HTTP 连通性检查接口。
 * author: zzy
 * created: 2026-10-19
 */
package ${groupId.replace('-', '_')}.${artifactId.replace('-', '_')}.trigger.http;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import ${groupId.replace('-', '_')}.${artifactId.replace('-', '_')}.types.model.ApiResponse;

/** 基础连通性检查；依赖就绪情况由 Actuator readiness 接口表达。 */
@RestController
public class HealthController {
    /**
     * GET /api/v1/ping，无参数、无写入副作用，不查询数据库或中间件。
     * @return HTTP 200，业务码 00000，data 为 null；不代表外部依赖就绪
     */
    @GetMapping("/api/v1/ping")
    public ApiResponse<Void> ping() {
        return ApiResponse.success(null);
    }
}
