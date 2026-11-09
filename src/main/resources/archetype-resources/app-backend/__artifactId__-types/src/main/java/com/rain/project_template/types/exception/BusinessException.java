#set( $dollar = '$' )
#set( $hash = '#' )
/*
 * description: 携带公开业务错误码、提示及可选底层原因。
 * author: zzy
 * created: 2026-10-19
 */
package ${groupId.replace('-', '_')}.${artifactId.replace('-', '_')}.types.exception;

import ${groupId.replace('-', '_')}.${artifactId.replace('-', '_')}.types.common.Constants.ResponseCode;

/**
 * 可预期的业务异常。不要把数据库、HTTP 客户端等基础设施异常直接暴露给接口层。
 */
public class BusinessException extends RuntimeException {
    /** 稳定的公开业务码；HTTP 状态映射由接口层负责。 */
    private final String code;

    /**
     * 使用集中定义的业务码和默认提示创建异常。
     * @param responseCode 非空的失败响应码
     */
    public BusinessException(ResponseCode responseCode) {
        this(responseCode.getCode(), responseCode.getInfo());
    }

    /**
     * 保留故障原因用于服务端诊断，默认提示可对外展示。
     * @param responseCode 非空的失败响应码
     * @param cause 原始异常，可为 null，不放入接口响应
     */
    public BusinessException(ResponseCode responseCode, Throwable cause) {
        this(responseCode.getCode(), responseCode.getInfo(), cause);
    }

    /**
     * 使用项目自定义错误码创建异常；不自动校验错误码或脱敏提示。
     * @param code 集中维护的业务错误码
     * @param message 可公开的错误提示
     * @param cause 仅用于服务端诊断的异常原因，可为 null
     */
    public BusinessException(String code, String message, Throwable cause) {
        super(message, cause);
        this.code = code;
    }

    /**
     * 为项目自定义业务码保留扩展入口。
     * @param code 应来自集中维护的错误码定义
     * @param message 可公开的错误提示，不直接使用基础设施异常消息
     */
    public BusinessException(String code, String message) {
        super(message);
        this.code = code;
    }

    public String code() {
        return code;
    }
}
