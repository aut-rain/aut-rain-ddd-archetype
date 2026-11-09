#set( $dollar = '$' )
#set( $hash = '#' )
/*
 * description: 集中维护跨模块业务响应码及默认提示。
 * author: zzy
 * created: 2026-11-02
 */
package ${groupId.replace('-', '_')}.${artifactId.replace('-', '_')}.types.common;

/** 跨模块通用常量。 */
public final class Constants {

    private Constants() {
    }

    /**
     * 统一业务响应码，参考《阿里巴巴 Java 开发手册》。
     *
     * <p>编码使用 5 位字符串，保留前导零：
     * 00000 表示执行成功；Axxxx 表示用户端错误（参数、访问权限等）；
     * Bxxxx 表示当前系统执行错误；Cxxxx 表示调用第三方服务错误。
     *
     * <p>业务响应码与 HTTP 状态码分别管理，HTTP 映射由接口层负责。
     * 已发布的响应码保持语义稳定，不重复分配；新增前查阅规范及已有定义。
     * code 用于程序判断，info 用于用户提示，不能根据提示文案判断业务分支。
     */
    public enum ResponseCode {
        SUCCESS("00000", "成功"),
        ILLEGAL_PARAMETER("A0400", "用户请求参数错误"),
        SYSTEM_ERROR("B0001", "系统执行出错"),
        THIRD_PARTY_ERROR("C0001", "调用第三方服务出错");

        /** 五位字符串业务码，保留前导零；不能作为 HTTP 状态码使用。 */
        private final String code;
        /** 默认公开提示，文案可调整，不作为客户端逻辑判断依据。 */
        private final String info;

        ResponseCode(String code, String info) {
            this.code = code;
            this.info = info;
        }

        public String getCode() {
            return code;
        }

        public String getInfo() {
            return info;
        }
    }
}
