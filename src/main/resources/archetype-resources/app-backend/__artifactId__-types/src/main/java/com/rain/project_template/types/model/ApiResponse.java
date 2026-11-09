#set( $dollar = '$' )
#set( $hash = '#' )
/*
 * description: 定义普通 JSON 接口的统一响应信封。
 * author: zzy
 * created: 2026-10-19
 */
package ${groupId.replace('-', '_')}.${artifactId.replace('-', '_')}.types.model;

import ${groupId.replace('-', '_')}.${artifactId.replace('-', '_')}.types.common.Constants.ResponseCode;

/**
 * 对外接口的统一响应包装。业务数据通过 data 返回，错误由 code/message 表达。
 *
 * @param <T> 业务数据类型，不包含 HTTP 状态信息
 * @param code 稳定的业务响应码；成功为字符串 00000，保留前导零
 * @param message 可公开的提示文案，不用于程序分支判断
 * @param data 业务数据；失败或无返回数据时为 null
 */
public record ApiResponse<T>(String code, String message, T data) {
    /**
     * 包装成功结果，不决定 HTTP 状态码。
     * @param <T> 返回数据类型
     * @param data 返回数据，可为 null
     * @return code 为 00000 的响应
     */
    public static <T> ApiResponse<T> success(T data) {
        return new ApiResponse<>(ResponseCode.SUCCESS.getCode(), ResponseCode.SUCCESS.getInfo(), data);
    }

    /**
     * 使用集中定义的错误码及默认提示构造失败结果。
     * @param <T> 调用方声明的数据类型；失败数据始终为 null
     * @param responseCode 非空的失败响应码，不应传入 SUCCESS
     * @return 不携带业务数据的失败响应
     */
    public static <T> ApiResponse<T> failure(ResponseCode responseCode) {
        return failure(responseCode.getCode(), responseCode.getInfo());
    }

    /**
     * 包装自定义业务错误；调用方负责错误码有效性与提示脱敏。
     * @param <T> 调用方声明的数据类型
     * @param code 集中维护的业务错误码，本方法不校验格式
     * @param message 可对外展示的提示，不传入底层异常详情
     * @return data 为 null 的失败响应
     */
    public static <T> ApiResponse<T> failure(String code, String message) {
        return new ApiResponse<>(code, message, null);
    }
}
