import { expect, test } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from './App';
import { AuthProvider } from './contexts/AuthContext';

test('renders the institutional login form', () => {
  render(<MemoryRouter initialEntries={['/login']}><AuthProvider><App /></AuthProvider></MemoryRouter>);
  expect(screen.getByRole('heading', { name: /bem-vinda de volta/i })).toBeDefined();
  expect(screen.getByLabelText('CPF')).toBeDefined();
  expect(screen.getByLabelText('Senha')).toBeDefined();
  expect(screen.getByRole('button', { name: /entrar/i })).toBeDefined();
});
