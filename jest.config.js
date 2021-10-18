module.exports = {
  // A list of paths to directories that Jest should use to search for files in
  roots: [
    "./src/"
  ],
  // Compile Typescript
  transform: {
    '^.+\\.(ts|tsx)$': 'ts-jest'
  },
  // Default value for FlareSolverr maxTimeout is 60000
  testTimeout: 70000
}
