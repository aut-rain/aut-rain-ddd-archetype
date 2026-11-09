#set( $dollar = '$' )
#set( $hash = '#' )
/*
 * description: 为领域和应用服务提供无外部依赖的参数守卫。
 * author: zzy
 * created: 2026-10-19
 */
package ${groupId.replace('-', '_')}.${artifactId.replace('-', '_')}.types.validation;

import ${groupId.replace('-', '_')}.${artifactId.replace('-', '_')}.types.exception.BusinessException;

/** 领域及应用服务的参数守卫；不进行数据库查询或关联归属校验。 */
public final class ValidationUtils {
    private ValidationUtils() {
    }

    /**
     * 校验非空并保留输入对象。
     * @param <T> 输入类型
     * @param value 待校验值
     * @param field 用于公开错误提示的字段名，不传入敏感值
     * @return 原始 value
     * @throws BusinessException value 为 null 时返回 VALIDATION_ERROR
     */
    public static <T> T requireNonNull(T value, String field) {
        if (value == null) {
            throw new BusinessException("VALIDATION_ERROR", field + " must not be null");
        }
        return value;
    }

    /**
     * 拒绝 null、空串和纯空白字符串，不修改文本内容。
     * @param value 待校验文本，不会自动 trim
     * @param field 用于公开错误提示的字段名，不传入敏感值
     * @return 原始 value，保留首尾空白
     * @throws BusinessException 文本无有效字符时返回 VALIDATION_ERROR
     */
    public static String requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new BusinessException("VALIDATION_ERROR", field + " must not be blank");
        }
        return value;
    }
}
