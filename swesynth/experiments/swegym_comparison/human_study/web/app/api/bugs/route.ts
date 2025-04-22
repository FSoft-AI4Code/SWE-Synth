import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { promises as fsPromises } from 'fs';

// Interface for our bug objects
interface Bug {
  instance_id: string;
  model_patch: string;
  problem_statement: string;
  issue_description: string;
  type: 'synthetic' | 'real';
}

// Cache to store our parsed bugs
let allSyntheticBugs: Bug[] = [];
let allRealBugs: Bug[] = [];
let loadedBugs: Bug[] = []; // Pre-loaded batch of bugs for quick serving
let isLoaded = false;
let syntheticBugsPath = '';
let realBugsPath = '';

// Track which bugs each user has already seen
const userSeenBugs: Record<string, Set<string>> = {};

// Constants for optimization
const BATCH_SIZE = 100; // Number of bugs to load in memory at once
const CACHE_SIZE = 30; // Number of bugs to keep ready for serving

// Function to initialize file paths
function initPaths() {
  syntheticBugsPath = path.join(process.cwd(), 'public', 'data', 'rq8_all_fake_bug_sample200_issues.jsonl');
  realBugsPath = path.join(process.cwd(), 'public', 'data', 'rq8_all_real_bug_sample200_issues.jsonl');
}

// Load all bugs at startup but only once
async function loadAllBugs() {
  try {
    if (!syntheticBugsPath) initPaths();
    
    // Load all synthetic bugs
    if (fs.existsSync(syntheticBugsPath)) {
      const syntheticContent = await fsPromises.readFile(syntheticBugsPath, 'utf8');
      const lines = syntheticContent.split('\n').filter(line => line.trim());
      
      allSyntheticBugs = lines.map(line => {
        const bug = JSON.parse(line);
        return {
          instance_id: bug.instance_id,
          model_patch: bug.model_patch,
          problem_statement: bug.problem_statement,
          issue_description: bug.issue_description,
          type: 'synthetic' as const
        };
      });
    }

    // Load all real bugs
    if (fs.existsSync(realBugsPath)) {
      const realContent = await fsPromises.readFile(realBugsPath, 'utf8');
      const lines = realContent.split('\n').filter(line => line.trim());
      
      allRealBugs = lines.map(line => {
        const bug = JSON.parse(line);
        return {
          instance_id: bug.instance_id,
          model_patch: bug.model_patch,
          problem_statement: bug.problem_statement,
          issue_description: bug.issue_description || createFallbackDescription(bug),
          type: 'real' as const
        };
      });
    }
    
    // Initial loaded bugs is empty, we'll fill it on demand
    loadedBugs = [];
    
    isLoaded = true;
    
    // If files don't exist, use mock data
    if (allSyntheticBugs.length === 0 && allRealBugs.length === 0) {
      loadMockData();
    }
    
    console.log(`Loaded ${allSyntheticBugs.length} synthetic bugs and ${allRealBugs.length} real bugs`);
    return { success: true, synthetic: allSyntheticBugs.length, real: allRealBugs.length };
  } catch (error) {
    console.error('Error loading all bugs:', error);
    return { success: false, error };
  }
}

// Function to get unseen bugs for a specific user
function getUnseenBugsForUser(userId: string, count: number): Bug[] {
  // Initialize seen bugs set for this user if it doesn't exist
  if (!userSeenBugs[userId]) {
    userSeenBugs[userId] = new Set<string>();
  }
  
  const userSeen = userSeenBugs[userId];
  const unseen: Bug[] = [];
  
  // Create a balanced mix of synthetic and real bugs
  const allBugs = [...allSyntheticBugs, ...allRealBugs];
  
  // Shuffle all bugs to ensure randomness
  const shuffledBugs = [...allBugs];
  shuffleArray(shuffledBugs);
  
  // Find bugs the user hasn't seen yet
  for (const bug of shuffledBugs) {
    if (!userSeen.has(bug.instance_id)) {
      unseen.push(bug);
      // Mark as seen
      userSeen.add(bug.instance_id);
      
      // Stop when we have enough
      if (unseen.length >= count) break;
    }
  }
  
  // If we don't have enough unseen bugs, reset and start over
  if (unseen.length < count && userSeen.size >= allBugs.length * 0.8) {
    console.log(`User ${userId} has seen most bugs, resetting their seen bugs list`);
    userSeenBugs[userId] = new Set<string>();
    
    // Add the current batch to the new seen set to avoid immediate duplicates
    unseen.forEach(bug => userSeenBugs[userId].add(bug.instance_id));
    
    // If we still need more bugs, get them from the shuffled list
    const additionalNeeded = count - unseen.length;
    if (additionalNeeded > 0) {
      for (const bug of shuffledBugs) {
        if (!userSeenBugs[userId].has(bug.instance_id)) {
          unseen.push(bug);
          userSeenBugs[userId].add(bug.instance_id);
          if (unseen.length >= count) break;
        }
      }
    }
  }
  
  return unseen;
}

// Create a fallback description if none exists
function createFallbackDescription(bug: any): string {
  return `# Bug Analysis\n\n## Problem\nThis code contains a bug that needs to be fixed.\n\n## Details\n${bug.problem_statement}\n\n## Code Location\nThe issue appears to be in the code shown in the diff.`;
}

// Shuffle array (Fisher-Yates algorithm)
function shuffleArray(array: any[]) {
  for (let i = array.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [array[i], array[j]] = [array[j], array[i]];
  }
}

// Load mock data for development
function loadMockData() {
  // Create some mock bugs for testing purposes
  allSyntheticBugs = [
    {
      instance_id: "synth1",
      model_patch: `function processArray(items) {
  // Bug: Using < instead of <= causes the last item to be skipped
  for (let i = 0; i < items.length - 1; i++) {
    items[i] = items[i] * 2;
  }
  return items;
}`,
      problem_statement: "This function should double every value in the array but has an off-by-one error.",
      issue_description: "# Off-by-One Error in Array Processing\n\n## Issue\nThe `processArray` function has an off-by-one error in its loop condition, causing it to skip processing the last element in the array.\n\n## Expected Behavior\nAll elements in the array should be doubled, including the last element.\n\n## Current Behavior\nThe function iterates through all elements except the last one, resulting in incomplete processing.\n\n## Root Cause\nThe loop condition `i < items.length - 1` stops iteration one element before the end of the array. The correct condition should be `i < items.length` or `i <= items.length - 1`.",
      type: "synthetic"
    },
    {
      instance_id: "synth2",
      model_patch: `def calculate_average(numbers):
    total = 0
    # Bug: Should check if numbers is empty before division
    for num in numbers:
        total += num
    return total / len(numbers)`,
      problem_statement: "This function calculates average but will fail with empty lists due to division by zero.",
      issue_description: "# Division by Zero in Average Calculation\n\n## Issue\nThe `calculate_average` function doesn't check if the input list is empty before dividing by its length, which can cause a division by zero error.\n\n## Expected Behavior\nThe function should handle empty lists gracefully, either by returning a default value (like 0) or raising a more descriptive error.\n\n## Steps to Reproduce\n1. Call `calculate_average` with an empty list: `calculate_average([])`\n2. Observe the division by zero error\n\n## Root Cause\nThe function unconditionally performs `total / len(numbers)` without checking if `len(numbers)` is zero.",
      type: "synthetic"
    }
  ];
  
  allRealBugs = [
    {
      instance_id: "real1",
      model_patch: `void updateUserData(User* user) {
  // Bug: No null check before dereferencing pointer
  user->lastLoginDate = getCurrentDate();
  user->loginCount++;
  saveUserToDatabase(user);
}`,
      problem_statement: "This function updates user data but can crash if the user pointer is null.",
      issue_description: "# Null Pointer Dereference in updateUserData\n\n## Issue\nThe `updateUserData` function directly accesses user pointer members without checking if the pointer is null, which can cause a segmentation fault.\n\n## Expected Behavior\nThe function should check if the user pointer is null before attempting to access its members.\n\n## Steps to Reproduce\n1. Call updateUserData with a NULL pointer\n2. Observe the application crash\n\n## Actual Result\nApplication crashes with segmentation fault.\n\n## Technical Details\nThe crash occurs at line `user->lastLoginDate = getCurrentDate();` when user is NULL.",
      type: "real"
    },
    {
      instance_id: "real2",
      model_patch: `public int convertStringToInt(String value) {
  // Bug: No validation if string is a valid number
  return Integer.parseInt(value);
}`,
      problem_statement: "This function converts strings to integers but doesn't validate the input.",
      issue_description: "# NumberFormatException in convertStringToInt\n\n## Issue\nThe `convertStringToInt` method doesn't validate if the input string contains a valid integer before parsing, which leads to uncaught NumberFormatException.\n\n## Expected Behavior\nThe method should either validate the input string or catch and handle NumberFormatException appropriately.\n\n## Steps to Reproduce\n1. Call convertStringToInt with a non-numeric string (e.g., \"abc\")\n2. Observe the uncaught exception\n\n## Actual Result\nUncaught NumberFormatException crashes the application.\n\n## Suggested Solution\nAdd try-catch block or input validation to handle invalid inputs gracefully.",
      type: "real"
    }
  ];

  loadedBugs = [...allSyntheticBugs, ...allRealBugs];
  shuffleArray(loadedBugs);
}

// Mark a bug as seen by a user
export async function POST(request: NextRequest) {
  try {
    const data = await request.json();
    const { userId, bugId } = data;
    
    if (!userId || !bugId) {
      return NextResponse.json({ success: false, error: 'Missing userId or bugId' }, { status: 400 });
    }
    
    // Initialize if needed
    if (!userSeenBugs[userId]) {
      userSeenBugs[userId] = new Set<string>();
    }
    
    // Mark as seen
    userSeenBugs[userId].add(bugId);
    
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error marking bug as seen:', error);
    return NextResponse.json({ success: false, error: 'Internal server error' }, { status: 500 });
  }
}

// GET handler for the bugs API
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const count = parseInt(searchParams.get('count') || '10');
  const userId = searchParams.get('userId');
  
  // If we need to load initial data
  if (!isLoaded) {
    await loadAllBugs();
  }
  
  let bugsToReturn: Bug[] = [];
  
  // If user ID is provided, get unseen bugs for that user
  if (userId) {
    bugsToReturn = getUnseenBugsForUser(userId, count);
  } else {
    // Fallback to random bugs if no user ID
    const allBugs = [...allSyntheticBugs, ...allRealBugs];
    const shuffled = [...allBugs];
    shuffleArray(shuffled);
    bugsToReturn = shuffled.slice(0, count);
  }
  
  // Return the bug data
  return NextResponse.json({ 
    bugs: bugsToReturn,
    count: {
      total: allSyntheticBugs.length + allRealBugs.length,
      returned: bugsToReturn.length,
      synthetic: allSyntheticBugs.length,
      real: allRealBugs.length,
      userSeen: userId ? userSeenBugs[userId]?.size || 0 : 0
    }
  });
} 