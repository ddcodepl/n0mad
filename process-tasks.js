const axios = require('axios');
const fs = require('fs-extra');
const path = require('path');
require('dotenv').config();

// Configuration constants
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000; // milliseconds

// Environment configuration
const config = {
  ticketsApiUrl: process.env.TICKETS_API_URL || 'http://localhost:3000/api',
  claudeApiUrl: process.env.CLAUDE_API_URL || 'https://api.anthropic.com/v1',
  claudeApiKey: process.env.CLAUDE_API_KEY,
  logToFile: process.env.LOG_TO_FILE === 'true',
  logFilePath: process.env.LOG_FILE_PATH || './task-processing.log',
  tasksSourceDir: process.env.TASKS_SOURCE_DIR || './tasks/tasks',
  tasksDestDir: process.env.TASKS_DEST_DIR || './.ticketmaster/tasks'
};

/**
 * Logging utility functions
 */
const logger = {
  log: (message, level = 'INFO') => {
    const timestamp = new Date().toISOString();
    const logEntry = `[${timestamp}] ${level}: ${message}`;
    
    console.log(logEntry);
    
    if (config.logToFile) {
      fs.appendFileSync(config.logFilePath, logEntry + '\n');
    }
  },
  
  info: (message) => logger.log(message, 'INFO'),
  warn: (message) => logger.log(message, 'WARN'),
  error: (message) => logger.log(message, 'ERROR'),
  debug: (message) => logger.log(message, 'DEBUG')
};

/**
 * Error handling utilities
 */
const withRetry = async (operation, retries = MAX_RETRIES) => {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      return await operation();
    } catch (error) {
      logger.warn(`Attempt ${attempt}/${retries} failed: ${error.message}`);
      
      if (attempt === retries) {
        throw error;
      }
      
      await new Promise(resolve => setTimeout(resolve, RETRY_DELAY * attempt));
    }
  }
};

/**
 * Fetch queued tasks from the Tickets API
 * @returns {Promise<Array>} Array of queued tasks
 */
async function fetchQueuedTasks() {
  logger.info('Fetching queued tasks from API');
  
  return withRetry(async () => {
    const response = await axios.get(`${config.ticketsApiUrl}/tasks/queued`);
    logger.info(`Found ${response.data.length} queued tasks`);
    return response.data;
  });
}

/**
 * Update task status and feedback via the Tickets API
 * @param {string} taskId - Task identifier
 * @param {string} status - New status (e.g., 'processing', 'done', 'failed')
 * @param {string} feedback - Optional feedback message
 * @returns {Promise<Object>} API response
 */
async function updateTaskStatus(taskId, status, feedback = null) {
  logger.info(`Updating task ${taskId} status to: ${status}`);
  
  return withRetry(async () => {
    const response = await axios.put(`${config.ticketsApiUrl}/tasks/${taskId}/status`, {
      status,
      feedback,
      timestamp: new Date().toISOString()
    });
    
    logger.info(`Task ${taskId} status updated successfully`);
    return response.data;
  });
}

/**
 * Copy task files from source to destination directory
 * @param {string} taskId - Task identifier
 * @returns {Promise<string>} Path to copied task file
 */
async function copyTaskFiles(taskId) {
  logger.info(`Copying task files for task: ${taskId}`);
  
  const sourceFile = path.join(config.tasksSourceDir, `${taskId}.json`);
  const destDir = config.tasksDestDir;
  const destFile = path.join(destDir, `${taskId}.json`);
  
  // Ensure destination directory exists
  await fs.ensureDir(destDir);
  
  // Copy the task file
  await fs.copy(sourceFile, destFile);
  
  logger.info(`Task file copied: ${sourceFile} -> ${destFile}`);
  return destFile;
}

/**
 * Invoke Claude API to process a task
 * @param {string} taskFilePath - Path to the task file
 * @param {string} prompt - Processing prompt
 * @param {boolean} skipPermissions - Whether to skip permissions
 * @returns {Promise<Object>} Claude API response
 */
async function invokeClaude(taskFilePath, prompt, skipPermissions = true) {
  logger.info(`Invoking Claude for task file: ${taskFilePath}`);
  
  return withRetry(async () => {
    const taskContent = await fs.readFile(taskFilePath, 'utf8');
    
    const response = await axios.post(`${config.claudeApiUrl}/messages`, {
      model: 'claude-3-sonnet-20240229',
      max_tokens: 4000,
      messages: [{
        role: 'user',
        content: `${prompt}\n\nTask Content:\n${taskContent}`
      }],
      skip_permissions: skipPermissions
    }, {
      headers: {
        'Authorization': `Bearer ${config.claudeApiKey}`,
        'Content-Type': 'application/json',
        'anthropic-version': '2023-06-01'
      }
    });
    
    logger.info('Claude processing completed successfully');
    return response.data;
  });
}

/**
 * Process a single task through the complete lifecycle
 * @param {Object} task - Task object from API
 * @returns {Promise<Object>} Processing result
 */
async function processTask(task) {
  const { id: taskId, prompt } = task;
  
  logger.info(`Starting processing for task: ${taskId}`);
  
  try {
    // Update status to processing
    await updateTaskStatus(taskId, 'processing');
    
    // Copy task files
    const taskFilePath = await copyTaskFiles(taskId);
    
    // Invoke Claude
    const claudeResponse = await invokeClaude(taskFilePath, prompt);
    
    // Update status to done with Claude response as feedback
    await updateTaskStatus(taskId, 'done', JSON.stringify(claudeResponse.content));
    
    logger.info(`Task ${taskId} processed successfully`);
    return { taskId, status: 'success', response: claudeResponse };
    
  } catch (error) {
    logger.error(`Error processing task ${taskId}: ${error.message}`);
    
    // Update status to failed
    await updateTaskStatus(taskId, 'failed', error.message);
    
    return { taskId, status: 'error', error: error.message };
  }
}

/**
 * Main execution function
 */
async function main() {
  logger.info('Starting task processing service');
  
  try {
    // Validate configuration
    if (!config.claudeApiKey) {
      throw new Error('CLAUDE_API_KEY environment variable is required');
    }
    
    // Fetch queued tasks
    const queuedTasks = await fetchQueuedTasks();
    
    if (queuedTasks.length === 0) {
      logger.info('No queued tasks found. Exiting.');
      return;
    }
    
    // Process each task
    const results = [];
    for (const task of queuedTasks) {
      const result = await processTask(task);
      results.push(result);
    }
    
    // Log summary
    const successful = results.filter(r => r.status === 'success').length;
    const failed = results.filter(r => r.status === 'error').length;
    
    logger.info(`Processing complete. Successful: ${successful}, Failed: ${failed}`);
    
  } catch (error) {
    logger.error(`Fatal error in main execution: ${error.message}`);
    process.exit(1);
  }
}

// Export functions for testing
module.exports = {
  fetchQueuedTasks,
  processTask,
  updateTaskStatus,
  invokeClaude,
  copyTaskFiles,
  logger,
  main
};

// Run main function if this script is executed directly
if (require.main === module) {
  main().catch(error => {
    console.error('Unhandled error:', error);
    process.exit(1);
  });
}