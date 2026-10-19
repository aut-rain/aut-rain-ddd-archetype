#set( $dollar = '$' )
#set( $hash = '#' )
package com.rain.${artifactId.replace('-', '_')}.types.exception;

/**
 * 可预期的业务异常。不要把数据库、HTTP 客户端等基础设施异常直接暴露给接口层。
 */
public class BusinessException extends RuntimeException {
    private final String code;

    public BusinessException(String code, String message) {
        super(message);
        this.code = code;
    }

    public String code() {
        return code;
    }
}
