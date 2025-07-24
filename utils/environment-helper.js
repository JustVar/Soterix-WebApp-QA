export function getEnvironmentConfig(env) {
  const currentEnv = env || process.env.TEST_ENV || 'uat';
  
  switch(currentEnv.toLowerCase()) {
    case 'qa':
      return require('../config/environments/qa.js');
    case 'uat':
    case 'stage':
      return require('../config/environments/uat.js');
    case 'prod':
    case 'demo':
      return require('../config/environments/prod.js');
    default:
      return require('../config/environments/uat.js');
  }
}

export function getCurrentEnvironment() {
  return process.env.TEST_ENV || 'uat';
}