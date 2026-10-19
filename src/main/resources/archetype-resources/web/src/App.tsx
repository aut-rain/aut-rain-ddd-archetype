#set( $dollar = '$' )
#set( $hash = '#' )
import { Layout, Typography } from 'antd';

export default function App() {
  return (
    <Layout className="app-shell">
      <Layout.Header><Typography.Text className="header-title">${projectName}</Typography.Text></Layout.Header>
      <Layout.Content className="app-content">
        <Typography.Title level={2}>项目已生成</Typography.Title>
        <Typography.Paragraph>从这里开始编写业务页面、接口和数据库迁移。</Typography.Paragraph>
      </Layout.Content>
    </Layout>
  );
}
