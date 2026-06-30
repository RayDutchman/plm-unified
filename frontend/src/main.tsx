import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

async function bootstrap() {
  // mock 模式：在渲染前装好 mock 适配层，确保首批请求即走假数据
  if (import.meta.env.VITE_USE_MOCK === '1') {
    const { installMock } = await import('./services/mock');
    installMock();
  }

  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}

bootstrap();
