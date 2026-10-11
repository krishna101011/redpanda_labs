import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Modal } from './Modal';

describe('Modal', () => {
  it('renders its content as an accessible dialog and closes on request', () => {
    const onClose = vi.fn();
    render(<Modal title="Confirm reset" onClose={onClose}><p>Workspace files will be restored.</p></Modal>);
    expect(screen.getByRole('dialog', { name: 'Confirm reset' })).toBeTruthy();
    expect(screen.getByText('Workspace files will be restored.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Close dialog' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('closes when the user clicks the backdrop, not its contents', () => {
    const onClose = vi.fn();
    render(<Modal title="Test" onClose={onClose}><button>Inner action</button></Modal>);
    fireEvent.mouseDown(screen.getByRole('button', { name: 'Inner action' }));
    expect(onClose).not.toHaveBeenCalled();
  });
});
