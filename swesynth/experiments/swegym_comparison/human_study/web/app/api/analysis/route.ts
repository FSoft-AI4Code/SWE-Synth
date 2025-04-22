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
  response_time: number;
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

// Interface for analysis results
interface AnalysisResults {
  overallStats: {
    totalUsers: number;
    totalResponses: number;
    avgResponsesPerUser: number;
    overallAccuracy: number;
    syntheticAccuracy: number;
    realAccuracy: number;
    confusionMatrix: {
      truePositives: number; // Correctly identified as synthetic
      falsePositives: number; // Identified as synthetic but was real
      trueNegatives: number; // Correctly identified as real
      falseNegatives: number; // Identified as real but was synthetic
    };
  };
  userBreakdown: {
    userId: string;
    userName: string;
    totalResponses: number;
    accuracy: number;
  }[];
  responseTimeStats: {
    avgResponseTime: number;
    medianResponseTime: number;
    minResponseTime: number;
    maxResponseTime: number;
  };
}

// Get all user results files
async function getAllUserResults(): Promise<UserResults[]> {
  const responsesDir = path.join(process.cwd(), 'data', 'responses');
  
  try {
    await fsPromises.access(responsesDir);
    
    const files = await fsPromises.readdir(responsesDir);
    const jsonFiles = files.filter(file => file.endsWith('.json'));
    
    const results: UserResults[] = [];
    
    for (const file of jsonFiles) {
      const filePath = path.join(responsesDir, file);
      const data = await fsPromises.readFile(filePath, 'utf8');
      try {
        const userResults = JSON.parse(data);
        results.push(userResults);
      } catch (e) {
        console.error(`Error parsing file ${file}:`, e);
      }
    }
    
    return results;
  } catch (error) {
    console.error('Error reading responses directory:', error);
    return [];
  }
}

// Generate analysis from all user results
function generateAnalysis(allResults: UserResults[]): AnalysisResults {
  // Count total users and responses
  const totalUsers = allResults.length;
  const allResponses = allResults.flatMap(user => user.responses);
  const totalResponses = allResponses.length;
  const avgResponsesPerUser = totalUsers > 0 ? totalResponses / totalUsers : 0;
  
  // Calculate overall accuracy
  const correctResponses = allResponses.filter(r => r.correct).length;
  const overallAccuracy = totalResponses > 0 ? correctResponses / totalResponses : 0;
  
  // Calculate accuracy for synthetic and real bugs
  const syntheticResponses = allResponses.filter(r => r.actual_type === 'synthetic');
  const syntheticCorrect = syntheticResponses.filter(r => r.correct).length;
  const syntheticAccuracy = syntheticResponses.length > 0 ? syntheticCorrect / syntheticResponses.length : 0;
  
  const realResponses = allResponses.filter(r => r.actual_type === 'real');
  const realCorrect = realResponses.filter(r => r.correct).length;
  const realAccuracy = realResponses.length > 0 ? realCorrect / realResponses.length : 0;
  
  // Calculate confusion matrix
  const truePositives = allResponses.filter(r => r.actual_type === 'synthetic' && r.user_response === 'synthetic').length;
  const falsePositives = allResponses.filter(r => r.actual_type === 'real' && r.user_response === 'synthetic').length;
  const trueNegatives = allResponses.filter(r => r.actual_type === 'real' && r.user_response === 'real').length;
  const falseNegatives = allResponses.filter(r => r.actual_type === 'synthetic' && r.user_response === 'real').length;
  
  // Calculate per-user breakdown
  const userBreakdown = allResults.map(user => ({
    userId: user.user_id,
    userName: user.user_name,
    totalResponses: user.responses.length,
    accuracy: user.responses.length > 0 
      ? user.responses.filter(r => r.correct).length / user.responses.length 
      : 0
  }));
  
  // Calculate response time statistics
  const responseTimes = allResponses.map(r => r.response_time).filter(t => t > 0);
  const avgResponseTime = responseTimes.length > 0 
    ? responseTimes.reduce((sum, time) => sum + time, 0) / responseTimes.length 
    : 0;
  
  // Calculate median response time
  const sortedTimes = [...responseTimes].sort((a, b) => a - b);
  const medianResponseTime = sortedTimes.length > 0 
    ? sortedTimes.length % 2 === 0
      ? (sortedTimes[sortedTimes.length / 2 - 1] + sortedTimes[sortedTimes.length / 2]) / 2
      : sortedTimes[Math.floor(sortedTimes.length / 2)]
    : 0;
  
  const minResponseTime = sortedTimes.length > 0 ? sortedTimes[0] : 0;
  const maxResponseTime = sortedTimes.length > 0 ? sortedTimes[sortedTimes.length - 1] : 0;
  
  return {
    overallStats: {
      totalUsers,
      totalResponses,
      avgResponsesPerUser,
      overallAccuracy,
      syntheticAccuracy,
      realAccuracy,
      confusionMatrix: {
        truePositives,
        falsePositives,
        trueNegatives,
        falseNegatives
      }
    },
    userBreakdown,
    responseTimeStats: {
      avgResponseTime,
      medianResponseTime,
      minResponseTime,
      maxResponseTime
    }
  };
}

// GET handler - Get analysis of all results
export async function GET(request: NextRequest) {
  try {
    const allResults = await getAllUserResults();
    
    if (allResults.length === 0) {
      return NextResponse.json({ 
        message: 'No user results found',
        data: {
          overallStats: {
            totalUsers: 0,
            totalResponses: 0,
            avgResponsesPerUser: 0,
            overallAccuracy: 0,
            syntheticAccuracy: 0,
            realAccuracy: 0,
            confusionMatrix: {
              truePositives: 0,
              falsePositives: 0,
              trueNegatives: 0,
              falseNegatives: 0
            }
          },
          userBreakdown: [],
          responseTimeStats: {
            avgResponseTime: 0,
            medianResponseTime: 0,
            minResponseTime: 0,
            maxResponseTime: 0
          }
        }
      });
    }
    
    const analysis = generateAnalysis(allResults);
    
    return NextResponse.json({
      message: 'Analysis generated successfully',
      data: analysis
    });
  } catch (error) {
    console.error('Error generating analysis:', error);
    return NextResponse.json({ error: 'Failed to generate analysis' }, { status: 500 });
  }
} 