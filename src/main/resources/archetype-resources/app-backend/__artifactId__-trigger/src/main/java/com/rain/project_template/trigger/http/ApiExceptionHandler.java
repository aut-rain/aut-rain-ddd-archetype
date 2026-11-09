#set( $dollar = '$' )
#set( $hash = '#' )
/*
 * description: 将业务异常和未知异常转换为统一 HTTP 响应。
 * author: zzy
 * created: 2026-10-19
 */
package ${groupId.replace('-', '_')}.${artifactId.replace('-', '_')}.trigger.http;

import ${groupId.replace('-', '_')}.${artifactId.replace('-', '_')}.types.common.Constants.ResponseCode;
import ${groupId.replace('-', '_')}.${artifactId.replace('-', '_')}.types.exception.BusinessException;
import ${groupId.replace('-', '_')}.${artifactId.replace('-', '_')}.types.model.ApiResponse;
import org.springframework.http.ResponseEntity;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/** 统一转换异常响应；业务异常提示必须由抛出方保证可公开。 */
@RestControllerAdvice
public class ApiExceptionHandler {
    /**
     * 按明确的业务码映射 HTTP 状态，不序列化异常及其 cause。
     * @param exception 业务异常，其 message 将直接返回给客户端
     * @return B0001 对应 500，C0001 对应 503，其余业务码默认对应 400
     */
    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ApiResponse<Void>> handleBusiness(BusinessException exception) {
        // 本项目的 HTTP 映射约定，不属于阿里业务响应码编码规则。
        HttpStatus status = HttpStatus.BAD_REQUEST;
        if (ResponseCode.SYSTEM_ERROR.getCode().equals(exception.code())) {
            status = HttpStatus.INTERNAL_SERVER_ERROR;
        } else if (ResponseCode.THIRD_PARTY_ERROR.getCode().equals(exception.code())) {
            status = HttpStatus.SERVICE_UNAVAILABLE;
        }
        return ResponseEntity.status(status).body(ApiResponse.failure(exception.code(), exception.getMessage()));
    }

    /**
     * 隐藏未知故障的内部细节，避免把存储和连接信息返回客户端。
     * @param exception 未被专用处理器接管的异常
     * @return HTTP 500 与 B0001 通用提示，data 为 null
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> handleUnexpected(Exception exception) {
        return ResponseEntity.internalServerError().body(ApiResponse.failure(ResponseCode.SYSTEM_ERROR));
    }
}
