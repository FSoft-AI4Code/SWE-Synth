import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { promises as fsPromises } from 'fs';

interface UserResponse {
  userId: string;
  userName: string;
  userEmail: string;
  bugId: string;
  actualType: 'synthetic' | 'real';
  userResponse: 'synthetic' | 'real';
  correct: boolean;
  responseTime: number;
  timestamp: string;
}

interface UserSummary {
  userId: string;
  userName: string;
  email: string;
  responses: UserResponse[];
  totalResponses: number;
  correctResponses: number;
  accuracy: number;
  syntheticCorrect: number;
  syntheticTotal: number;
  syntheticAccuracy: number;
  realCorrect: number;
  realTotal: number;
  realAccuracy: number;
  pValue: number;
  averageResponseTime: number;
}

// Calculate p-value using binomial test approximation
function calculatePValue(correct: number, total: number): number {
  const proportion = correct / total;
  
  // If the total is too small, return 1.0 (not significant)
  if (total < 10) return 1.0;
  
  // Calculate standard error under null hypothesis (p = 0.5)
  const standardError = Math.sqrt(0.5 * 0.5 / total);
  
  // Calculate z-score
  const zScore = Math.abs((proportion - 0.5) / standardError);
  
  // Convert z-score to p-value (approximation)
  const pValue = 2 * (1 - Math.min(0.9999, normalCDF(zScore)));
  
  return pValue;
}

// Approximation of the normal cumulative distribution function
function normalCDF(x: number): number {
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
  
  // Formula
  const t = 1.0 / (1.0 + p * x);
  const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
  
  return 0.5 * (1 + sign * y);
}

export async function GET(request: NextRequest) {
  try {
    // Check if the user is authorized (we would typically check this more thoroughly)
    const { searchParams } = new URL(request.url);
    const userId = searchParams.get('userId');
    
    // Get responses data
    const responsesPath = path.join(process.cwd(), 'data', 'responses.json');
    let allResponses: UserResponse[] = [];
    
    if (fs.existsSync(responsesPath)) {
      const content = await fsPromises.readFile(responsesPath, 'utf8');
      allResponses = JSON.parse(content);
    } else {
      // If file doesn't exist, return empty stats
      return NextResponse.json({ 
        stats: {
          totalUsers: 0,
          totalResponses: 0,
          overallAccuracy: 0,
          syntheticAccuracy: 0,
          realAccuracy: 0,
          averageResponseTime: 0,
          significantUsers: 0,
          usersAboveChance: 0,
          userStats: [],
          responseDistribution: {
            syntheticCorrect: 0,
            syntheticIncorrect: 0,
            realCorrect: 0,
            realIncorrect: 0
          }
        } 
      });
    }
    
    // Get unique users
    const users = [...new Set(allResponses.map(r => r.userId))].map(userId => {
      const userResponses = allResponses.filter(r => r.userId === userId);
      const firstResponse = userResponses[0]; // Get user details from first response
      
      // Count statistics
      const totalResponses = userResponses.length;
      const correctResponses = userResponses.filter(r => r.correct).length;
      const accuracy = correctResponses / totalResponses;
      
      // Synthetic accuracy
      const syntheticResponses = userResponses.filter(r => r.actualType === 'synthetic');
      const syntheticCorrect = syntheticResponses.filter(r => r.correct).length;
      const syntheticAccuracy = syntheticResponses.length > 0 ? syntheticCorrect / syntheticResponses.length : 0;
      
      // Real accuracy
      const realResponses = userResponses.filter(r => r.actualType === 'real');
      const realCorrect = realResponses.filter(r => r.correct).length;
      const realAccuracy = realResponses.length > 0 ? realCorrect / realResponses.length : 0;
      
      // Calculate p-value
      const pValue = calculatePValue(correctResponses, totalResponses);
      
      // Average response time
      const avgResponseTime = userResponses.reduce((sum, r) => sum + r.responseTime, 0) / totalResponses;
      
      return {
        userId,
        userName: firstResponse.userName,
        email: firstResponse.userEmail,
        responses: userResponses,
        totalResponses,
        correctResponses,
        accuracy,
        syntheticCorrect,
        syntheticTotal: syntheticResponses.length,
        syntheticAccuracy,
        realCorrect,
        realTotal: realResponses.length,
        realAccuracy,
        pValue,
        averageResponseTime: avgResponseTime
      };
    });
    
    // Calculate overall statistics
    const totalUsers = users.length;
    const totalResponses = allResponses.length;
    
    // Overall accuracy
    const correctResponses = allResponses.filter(r => r.correct).length;
    const overallAccuracy = totalResponses > 0 ? correctResponses / totalResponses : 0;
    
    // Synthetic accuracy
    const syntheticResponses = allResponses.filter(r => r.actualType === 'synthetic');
    const syntheticCorrect = syntheticResponses.filter(r => r.correct).length;
    const syntheticAccuracy = syntheticResponses.length > 0 ? syntheticCorrect / syntheticResponses.length : 0;
    
    // Real accuracy
    const realResponses = allResponses.filter(r => r.actualType === 'real');
    const realCorrect = realResponses.filter(r => r.correct).length;
    const realAccuracy = realResponses.length > 0 ? realCorrect / realResponses.length : 0;
    
    // Average response time
    const averageResponseTime = allResponses.reduce((sum, r) => sum + r.responseTime, 0) / totalResponses;
    
    // Statistically significant users
    const significantUsers = users.filter(user => user.pValue < 0.05).length;
    const usersAboveChance = users.filter(user => user.accuracy > 0.5).length;
    
    // Response distribution
    const responseDistribution = {
      syntheticCorrect,
      syntheticIncorrect: syntheticResponses.length - syntheticCorrect,
      realCorrect,
      realIncorrect: realResponses.length - realCorrect
    };
    
    // Prepare user stats for frontend
    const userStats = users.map(user => ({
      userId: user.userId,
      userName: user.userName,
      email: user.email,
      totalResponses: user.totalResponses,
      accuracy: user.accuracy,
      syntheticAccuracy: user.syntheticAccuracy,
      realAccuracy: user.realAccuracy,
      pValue: user.pValue
    }));
    
    // Return the stats
    return NextResponse.json({
      stats: {
        totalUsers,
        totalResponses,
        overallAccuracy,
        syntheticAccuracy,
        realAccuracy,
        averageResponseTime,
        significantUsers,
        usersAboveChance,
        userStats,
        responseDistribution
      }
    });
  } catch (error) {
    console.error('Error generating summary:', error);
    return NextResponse.json(
      { error: 'Failed to generate summary' },
      { status: 500 }
    );
  }
} 