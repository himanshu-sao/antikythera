module.exports = {
  // preset: 'ts-jest',  // removed in favor of Babel for all files
  testEnvironment: 'jsdom',
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json', 'node'],
  transform: {
    "^.+\\.(js|jsx|ts|tsx)$": ["babel-jest", { "presets": ["@babel/preset-react", "@babel/preset-typescript"] }],
  },
  testPathIgnorePatterns: ['e2e/', 'ui/e2e-tests/', '\\.spec\\.ts$', 'ManagementModals.test.tsx', 'App.polling.test.tsx', 'Sidebar.test.tsx'],
  transformIgnorePatterns: [],
  setupFilesAfterEnv: ['@testing-library/jest-dom'],
};
