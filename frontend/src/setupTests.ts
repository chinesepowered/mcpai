/**
 * Global test setup for the React application.
 *
 * The goal is to keep the configuration **minimal**:
 * 1. Enable Testing-Library matchers.
 * 2. Ensure the DOM is cleaned after each test (if the current test runner
 *    exposes `afterEach`).
 * 3. Provide very light mocks for APIs that are missing in jsdom (e.g.
 *    `matchMedia`, `IntersectionObserver`).
 *
 * NOTE:  We purposefully avoid using `jest.fn()` / `vi.fn()` or any other test
 * framework helpers to keep this file framework-agnostic.
 */

import '@testing-library/jest-dom';
import { cleanup } from '@testing-library/react';

/* -------------------------------------------------------------------------- */
/*                               Global hooks                                */
/* -------------------------------------------------------------------------- */

// Automatically clean up the DOM after every test if the runner supports it.
if (typeof afterEach === 'function') {
  // eslint-disable-next-line @typescript-eslint/ban-ts-comment
  // @ts-ignore - `afterEach` is injected by the test runner (Vitest / Jest).
  afterEach(() => {
    cleanup();
  });
}

/* -------------------------------------------------------------------------- */
/*                               Basic  mocks                                */
/* -------------------------------------------------------------------------- */

// Mock `window.matchMedia` (used by many CSS-in-JS libraries and Tailwind's
// dark-mode utility).
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    // No-op listener methods — sufficient for most component tests.
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// Mock `IntersectionObserver` (used by lazy-loading images, etc.).
class MockIntersectionObserver {
  observe() {/* noop */}
  unobserve() {/* noop */}
  disconnect() {/* noop */}
}

Object.defineProperty(window, 'IntersectionObserver', {
  writable: true,
  configurable: true,
  value: MockIntersectionObserver,
});
