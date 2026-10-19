#set( $dollar = '$' )
#set( $hash = '#' )
import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import App from './App';

it('renders the generated landing page', () => {
  render(<App />);
  expect(screen.getByRole('heading', { name: '项目已生成' })).toBeInTheDocument();
});
