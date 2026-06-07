module.exports = {
  testPathIgnorePatterns: ['/tests/', '/e2e-tests/'],
  testEnvironment: 'jsdom',
  transform: {
    '^.+\\.(js|jsx|ts|tsx)$': 'babel-jest',
  },
  moduleFileExtensions: ['js','jsx','ts','tsx'],
  moduleNameMapper: {
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
    '\\.(svg|png|jpg|jpeg|gif)$': '<rootDir>/__mocks__/fileMock.js'
  },
  setupFilesAfterEnv: ['@testing-library/jest-dom'],
};
