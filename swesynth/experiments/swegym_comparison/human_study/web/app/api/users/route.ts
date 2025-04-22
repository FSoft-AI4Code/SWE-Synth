import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { promises as fsPromises } from 'fs';

// Interface for user objects
interface User {
  id: string;
  name: string;
  email: string;
  created_at: string;
}

// Path to the users data file
const USERS_FILE_PATH = path.join(process.cwd(), 'data', 'users.json');

// Ensure data directory exists
async function ensureDataDirExists() {
  const dataDir = path.join(process.cwd(), 'data');
  try {
    await fsPromises.access(dataDir);
  } catch (error) {
    // Directory doesn't exist, create it
    await fsPromises.mkdir(dataDir, { recursive: true });
  }
}

// Load all users
async function loadUsers(): Promise<User[]> {
  await ensureDataDirExists();
  
  try {
    await fsPromises.access(USERS_FILE_PATH);
    const data = await fsPromises.readFile(USERS_FILE_PATH, 'utf8');
    return JSON.parse(data);
  } catch (error) {
    // File doesn't exist or can't be parsed
    return [];
  }
}

// Save users to file
async function saveUsers(users: User[]): Promise<void> {
  await ensureDataDirExists();
  await fsPromises.writeFile(USERS_FILE_PATH, JSON.stringify(users, null, 2), 'utf8');
}

// Create a new user
async function createUser(name: string, email: string): Promise<User> {
  const users = await loadUsers();
  
  // Check if user already exists
  const existingUser = users.find(user => user.email === email);
  if (existingUser) {
    return existingUser;
  }
  
  // Create new user
  const newUser: User = {
    id: Date.now().toString(36) + Math.random().toString(36).substring(2), // Generate unique ID
    name,
    email,
    created_at: new Date().toISOString(),
  };
  
  users.push(newUser);
  await saveUsers(users);
  
  return newUser;
}

// Get user by ID
async function getUserById(id: string): Promise<User | null> {
  const users = await loadUsers();
  return users.find(user => user.id === id) || null;
}

// GET handler - Get user by ID
export async function GET(request: NextRequest) {
  const userId = request.nextUrl.searchParams.get('id');
  
  if (!userId) {
    return NextResponse.json({ error: 'User ID is required' }, { status: 400 });
  }
  
  const user = await getUserById(userId);
  
  if (!user) {
    return NextResponse.json({ error: 'User not found' }, { status: 404 });
  }
  
  return NextResponse.json(user);
}

// POST handler - Create new user
export async function POST(request: NextRequest) {
  try {
    const { name, email } = await request.json();
    
    if (!name || !email) {
      return NextResponse.json({ error: 'Name and email are required' }, { status: 400 });
    }
    
    const user = await createUser(name, email);
    
    return NextResponse.json(user);
  } catch (error) {
    console.error('Error creating user:', error);
    return NextResponse.json({ error: 'Failed to create user' }, { status: 500 });
  }
} 