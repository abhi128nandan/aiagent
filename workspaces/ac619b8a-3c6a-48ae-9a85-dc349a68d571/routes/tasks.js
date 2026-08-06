import express from 'express';
import { getTasks, createTask, getTaskById, updateTask, deleteTask } from '../controllers/taskController.js';

const router = express.Router();

// GET all tasks
router.get('/', getTasks);

// POST new task
router.post('/', createTask);

// GET single task by ID
router.get('/:id', getTaskById);

// PUT update task
router.put('/:id', updateTask);

// DELETE task
router.delete('/:id', deleteTask);

export default router;