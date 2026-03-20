export interface User {
  client_id: string
  email: string
  company_name: string
  subscription_tier: 'free' | 'pro' | 'enterprise'
}

export interface LoginCredentials {
  email: string
  password: string
}

export interface RegisterData {
  email: string
  password: string
  company_name: string
  phone_number: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

export interface Campaign {
  campaign_id: string
  campaign_code: string
  name: string
  description?: string
  campaign_type: string
  status: string
  start_date: string
  end_date?: string
  created_at: string
}

export interface Photo {
  photo_id: string
  campaign_code: string
  vendor_id: string
  timestamp: string
  verification_status: string
  match_confidence?: number
  s3_url?: string
}

export interface CampaignStatistics {
  campaign: {
    code: string
    name: string
    type: string
    status: string
  }
  statistics: {
    total_photos: number
    status_counts: Record<string, number>
    average_confidence: number
    flagged_photos: number
    vendor_counts: Record<string, number>
    audit_flag_counts: Record<string, number>
  }
  raw_data: {
    confidence_scores: number[]
    timestamps: string[]
  }
}


// Bulk Operations Types
export interface BulkOperationRow {
  row: number
  error: string
}

export interface BulkOperationResponse {
  created: any[]
  errors: BulkOperationRow[]
}


export interface PhotoLocation {
  photo_id: string
  campaign_name: string
  campaign_code: string
  confidence_score: number
  vendor_id: string
  timestamp: string
  verification_status: string
  latitude: number
  longitude: number
  match_confidence?: number
  s3_url?: string
}
