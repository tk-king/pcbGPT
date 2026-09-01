import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import 'katex/dist/katex.min.css'
import '@mantine/core/styles.css';
import App from './App.jsx'
import { MantineProvider } from '@mantine/core';
import pcbGptTheme from './theme/theme.js'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <MantineProvider theme={pcbGptTheme}>
      <App />
    </MantineProvider>
  </StrictMode>,
)
