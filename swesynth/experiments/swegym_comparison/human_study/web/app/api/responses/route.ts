import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { promises as fsPromises } from 'fs';

// Interface for user response objects
interface UserResponse {
  user_id: string;
  bug_id: string;
  actual_type: 'synthetic' | 'real';
  user_response: 'synthetic' | 'real';
  correct: boolean;
  response_time: number; // Time taken to respond in milliseconds
  timestamp: string;
}

// Interface for user results
interface UserResults {
  user_id: string;
  user_name: string;
  user_email: string;
  responses: UserResponse[];
  summary?: {
    total_responses: number;
    correct_responses: number;
    accuracy: number;
    p_value: number;
    synthetic_accuracy: number;
    real_accuracy: number;
  };
}

// Implementation of error function (erf)
// Used for statistical calculations
function erf(x: number): number {
  // Constants for approximation
  const a1 = 0.254829592;
  const a2 = -0.284496736;
  const a3 = 1.421413741;
  const a4 = -1.453152027;
  const a5 = 1.061405429;
  const p = 0.3275911;

  // Save the sign of x
  const sign = x < 0 ? -1 : 1;
  x = Math.abs(x);

  // Formula for approximation
  const t = 1.0 / (1.0 + p * x);
  const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);

  return sign * y;
}

// Ensure data directory exists
async function ensureDataDirExists() {
  const dataDir = path.join(process.cwd(), 'data', 'responses');
  try {
    await fsPromises.access(dataDir);
  } catch (error) {
    // Directory doesn't exist, create it
    await fsPromises.mkdir(dataDir, { recursive: true });
  }
}

// Get the file path for a user's responses
function getUserResponsesPath(userId: string): string {
  return path.join(process.cwd(), 'data', 'responses', `${userId}.json`);
}

// Load a user's responses
async function loadUserResponses(userId: string): Promise<UserResults | null> {
  await ensureDataDirExists();
  
  const filePath = getUserResponsesPath(userId);
  
  try {
    await fsPromises.access(filePath);
    const data = await fsPromises.readFile(filePath, 'utf8');
    return JSON.parse(data);
  } catch (error) {
    // File doesn't exist or can't be parsed
    return null;
  }
}

// Save a user's responses
async function saveUserResponses(results: UserResults): Promise<void> {
  await ensureDataDirExists();
  const filePath = getUserResponsesPath(results.user_id);
  await fsPromises.writeFile(filePath, JSON.stringify(results, null, 2), 'utf8');
}

// Add a response to a user's results
async function addUserResponse(userId: string, userName: string, userEmail: string, response: Omit<UserResponse, 'timestamp'>): Promise<UserResults> {
  let userResults = await loadUserResponses(userId);
  
  if (!userResults) {
    userResults = {
      user_id: userId,
      user_name: userName,
      user_email: userEmail,
      responses: [],
    };
  }
  
  const newResponse: UserResponse = {
    ...response,
    timestamp: new Date().toISOString(),
  };
  
  userResults.responses.push(newResponse);
  
  // Update summary statistics
  const totalResponses = userResults.responses.length;
  const correctResponses = userResults.responses.filter(r => r.correct).length;
  const accuracy = correctResponses / totalResponses;
  
  // Calculate p-value using binomial test approximation
  const standardError = Math.sqrt(0.5 * 0.5 / totalResponses);
  const zScore = Math.abs((accuracy - 0.5) / standardError);
  const pValue = 2 * (1 - Math.min(0.9999, 0.5 * (1 + erf(zScore / Math.sqrt(2)))));
  
  // Calculate accuracy for synthetic vs real bugs
  const syntheticResponses = userResults.responses.filter(r => r.actual_type === 'synthetic');
  const syntheticCorrect = syntheticResponses.filter(r => r.correct).length;
  const syntheticAccuracy = syntheticResponses.length > 0 ? syntheticCorrect / syntheticResponses.length : 0;
  
  const realResponses = userResults.responses.filter(r => r.actual_type === 'real');
  const realCorrect = realResponses.filter(r => r.correct).length;
  const realAccuracy = realResponses.length > 0 ? realCorrect / realResponses.length : 0;
  
  userResults.summary = {
    total_responses: totalResponses,
    correct_responses: correctResponses,
    accuracy,
    p_value: pValue,
    synthetic_accuracy: syntheticAccuracy,
    real_accuracy: realAccuracy
  };
  
  await saveUserResponses(userResults);
  
  return userResults;
}

// GET handler - Get a user's responses
export async function GET(request: NextRequest) {
  const userId = request.nextUrl.searchParams.get('userId');
  
  if (!userId) {
    return NextResponse.json({ error: 'User ID is required' }, { status: 400 });
  }
  
  const userResults = await loadUserResponses(userId);
  
  if (!userResults) {
    return NextResponse.json({ error: 'No responses found for this user' }, { status: 404 });
  }
  
  return NextResponse.json(userResults);
}

// POST handler - Save a user's response
export async function POST(request: NextRequest) {
  try {
    const { 
      userId, 
      userName, 
      userEmail, 
      bugId, 
      actualType, 
      userResponse, 
      responseTime 
    } = await request.json();
    
    if (!userId || !userName || !userEmail || !bugId || !actualType || !userResponse) {
      return NextResponse.json({ 
        error: 'Missing required fields' 
      }, { status: 400 });
    }
    
    const correct = actualType === userResponse;
    
    const response: Omit<UserResponse, 'timestamp'> = {
      user_id: userId,
      bug_id: bugId,
      actual_type: actualType,
      user_response: userResponse,
      correct,
      response_time: responseTime || 0
    };
    
    const userResults = await addUserResponse(userId, userName, userEmail, response);
    
    return NextResponse.json(userResults);
  } catch (error) {
    console.error('Error saving response:', error);
    return NextResponse.json({ error: 'Failed to save response' }, { status: 500 });
  }
} 