// Run with: npx tsx --env-file=.env.local scripts/audit_r010_data.ts

import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY! || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)

async function audit() {
  const PROFILE_ID = 'R010'

  // 1. trade_imports
  console.log('\n========== TRADE_IMPORTS ==========\n')
  const { data: tradeData, error: tradeErr } = await supabase
    .from('trade_imports')
    .select('*')
    .eq('profile_id', PROFILE_ID)
    .order('created_at', { ascending: false })
    .limit(1)
    .single()

  if (tradeErr) console.log('trade_imports error:', tradeErr.message)
  if (tradeData) {
    console.log('Top-level columns:', Object.keys(tradeData))
    console.log('\nraw_result top-level keys:', Object.keys(tradeData.raw_result || {}))

    const rr = tradeData.raw_result
    if (rr?.classification_v2) {
      console.log('\nclassification_v2 keys:', Object.keys(rr.classification_v2))
      if (rr.classification_v2.dimensions) {
        console.log('dimensions keys:', Object.keys(rr.classification_v2.dimensions))
        // Print first dimension to see shape
        const firstDim = Object.keys(rr.classification_v2.dimensions)[0]
        console.log(`dimensions.${firstDim} value:`, JSON.stringify(rr.classification_v2.dimensions[firstDim], null, 2))
      }
    }

    if (rr?.narrative) {
      console.log('\nnarrative keys:', Object.keys(rr.narrative))
      // Print first 200 chars of headline
      if (rr.narrative.headline) console.log('narrative.headline:', rr.narrative.headline.substring(0, 200))
    }

    if (rr?.features) {
      const featureKeys = Object.keys(rr.features)
      console.log('\nfeatures count:', featureKeys.length)
      console.log('first 20 feature keys:', featureKeys.slice(0, 20))
      // Print a few sample values
      console.log('\nSample feature values:')
      for (const key of featureKeys.slice(0, 10)) {
        console.log(`  ${key}:`, rr.features[key])
      }
    }

    if (rr?.summary_stats) {
      console.log('\nsummary_stats:', JSON.stringify(rr.summary_stats, null, 2))
    }

    if (rr?.round_trips) {
      console.log('\nround_trips count:', rr.round_trips.length)
      if (rr.round_trips[0]) {
        console.log('first round_trip keys:', Object.keys(rr.round_trips[0]))
        console.log('first round_trip:', JSON.stringify(rr.round_trips[0], null, 2))
      }
    }
  }

  // 2. portfolio_imports
  console.log('\n========== PORTFOLIO_IMPORTS ==========\n')
  const { data: portfolioData, error: portfolioErr } = await supabase
    .from('portfolio_imports')
    .select('*')
    .eq('profile_id', PROFILE_ID)
    .order('created_at', { ascending: false })
    .limit(1)
    .single()

  if (portfolioErr) console.log('portfolio_imports error:', portfolioErr.message)
  if (portfolioData) {
    console.log('Top-level columns:', Object.keys(portfolioData))

    if (portfolioData.portfolio_analysis) {
      console.log('\nportfolio_analysis keys:', Object.keys(portfolioData.portfolio_analysis))
      // Print each section's keys
      for (const [key, val] of Object.entries(portfolioData.portfolio_analysis)) {
        if (val && typeof val === 'object') {
          console.log(`  ${key} keys:`, Object.keys(val as object))
        } else {
          console.log(`  ${key}:`, JSON.stringify(val).substring(0, 150))
        }
      }
    }

    if (portfolioData.instrument_breakdown) {
      console.log('\ninstrument_breakdown keys:', Object.keys(portfolioData.instrument_breakdown))
      // If there's a features sub-key
      if (portfolioData.instrument_breakdown.features) {
        console.log('features keys:', Object.keys(portfolioData.instrument_breakdown.features))
        console.log('features values:', JSON.stringify(portfolioData.instrument_breakdown.features, null, 2))
      } else {
        // Maybe features are at top level
        console.log('instrument_breakdown sample:', JSON.stringify(portfolioData.instrument_breakdown, null, 2).substring(0, 500))
      }
    }

    if (portfolioData.reconstructed_holdings) {
      const holdings = portfolioData.reconstructed_holdings
      if (Array.isArray(holdings)) {
        console.log('\nreconstructed_holdings count:', holdings.length)
        if (holdings[0]) console.log('first holding keys:', Object.keys(holdings[0]))
      } else if (typeof holdings === 'object') {
        console.log('\nreconstructed_holdings keys:', Object.keys(holdings))
        // Might be grouped by account
        const firstKey = Object.keys(holdings)[0]
        if (firstKey) {
          const firstGroup = (holdings as Record<string, unknown>)[firstKey]
          if (Array.isArray(firstGroup) && firstGroup[0]) {
            console.log(`first account (${firstKey}) first holding:`, JSON.stringify(firstGroup[0], null, 2))
          }
        }
      }
    }

    if (portfolioData.accounts_detected) {
      console.log('\naccounts_detected:', JSON.stringify(portfolioData.accounts_detected, null, 2))
    }

    if (portfolioData.account_summaries) {
      console.log('\naccount_summaries keys:', Object.keys(portfolioData.account_summaries))
      const firstAcct = Object.keys(portfolioData.account_summaries)[0]
      if (firstAcct) {
        console.log(`first account summary (${firstAcct}):`, JSON.stringify(portfolioData.account_summaries[firstAcct], null, 2).substring(0, 500))
      }
    }
  }

  // 3. behavioral_profiles
  console.log('\n========== BEHAVIORAL_PROFILES ==========\n')
  const { data: profileData, error: profileErr } = await supabase
    .from('behavioral_profiles')
    .select('*')
    .eq('id', PROFILE_ID)
    .single()

  if (profileErr) console.log('behavioral_profiles error:', profileErr.message)
  if (profileData) {
    console.log('Top-level columns:', Object.keys(profileData))
    console.log('Non-JSONB values:')
    for (const [key, val] of Object.entries(profileData)) {
      if (typeof val !== 'object' || val === null) {
        console.log(`  ${key}:`, val)
      }
    }

    if (profileData.features) {
      const fKeys = Object.keys(profileData.features as object)
      console.log('\nfeatures key count:', fKeys.length)
      console.log('first 20 keys:', fKeys.slice(0, 20))
    }

    if (profileData.classification) {
      console.log('\nclassification:', JSON.stringify(profileData.classification, null, 2).substring(0, 500))
    }

    if (profileData.holdings_profile) {
      console.log('\nholdings_profile keys:', Object.keys(profileData.holdings_profile as object))
    }

    if (profileData.metadata) {
      console.log('\nmetadata:', JSON.stringify(profileData.metadata, null, 2).substring(0, 500))
    }
  }

  // 4. Also check the V2 tables that the behavioral-mirror writes to
  console.log('\n========== V2 TABLES (uploads, analysis_results, profiles_new) ==========\n')

  // uploads
  const { data: uploadsData, error: uploadsErr } = await supabase
    .from('uploads')
    .select('*')
    .eq('profile_id', PROFILE_ID)
    .order('created_at', { ascending: false })
    .limit(1)
    .single()

  if (uploadsErr) console.log('uploads error:', uploadsErr.message)
  if (uploadsData) {
    console.log('uploads top-level columns:', Object.keys(uploadsData))
    console.log('uploads non-JSONB values:')
    for (const [key, val] of Object.entries(uploadsData)) {
      if (typeof val !== 'object' || val === null) {
        console.log(`  ${key}:`, val)
      }
    }
  }

  // analysis_results
  const { data: analysisRows, error: analysisErr } = await supabase
    .from('analysis_results')
    .select('*')
    .eq('profile_id', PROFILE_ID)
    .order('created_at', { ascending: false })

  if (analysisErr) console.log('analysis_results error:', analysisErr.message)
  if (analysisRows && analysisRows.length > 0) {
    console.log('\nanalysis_results: found', analysisRows.length, 'rows')
    for (const row of analysisRows) {
      console.log(`\n--- analysis_type: ${row.analysis_type} ---`)
      console.log('columns:', Object.keys(row))

      if (row.features && typeof row.features === 'object') {
        const fKeys = Object.keys(row.features)
        console.log('features key count:', fKeys.length)
        console.log('first 20 feature keys:', fKeys.slice(0, 20))
        // Print a few sample values
        console.log('Sample feature values:')
        for (const key of fKeys.slice(0, 5)) {
          console.log(`  ${key}:`, row.features[key])
        }
      }

      if (row.narrative && typeof row.narrative === 'object') {
        console.log('narrative keys:', Object.keys(row.narrative))
      } else if (typeof row.narrative === 'string') {
        console.log('narrative (first 200 chars):', row.narrative.substring(0, 200))
      }

      if (row.summary_stats) {
        console.log('summary_stats:', JSON.stringify(row.summary_stats, null, 2).substring(0, 500))
      }

      if (row.account_summaries) {
        console.log('account_summaries keys:', Object.keys(row.account_summaries))
        const firstAcct = Object.keys(row.account_summaries)[0]
        if (firstAcct) {
          console.log(`first account (${firstAcct}):`, JSON.stringify(row.account_summaries[firstAcct], null, 2).substring(0, 500))
        }
      }

      if (row.classification) {
        console.log('classification:', JSON.stringify(row.classification, null, 2).substring(0, 800))
      }

      if (row.round_trips) {
        const rt = row.round_trips
        if (Array.isArray(rt)) {
          console.log('round_trips count:', rt.length)
          if (rt[0]) {
            console.log('first round_trip keys:', Object.keys(rt[0]))
            console.log('first round_trip:', JSON.stringify(rt[0], null, 2))
          }
        }
      }
    }
  }

  // profiles_new
  const { data: profileNewData, error: profileNewErr } = await supabase
    .from('profiles_new')
    .select('*')
    .eq('id', PROFILE_ID)
    .single()

  if (profileNewErr) console.log('\nprofiles_new error:', profileNewErr.message)
  if (profileNewData) {
    console.log('\nprofiles_new top-level columns:', Object.keys(profileNewData))
    console.log('profiles_new non-JSONB values:')
    for (const [key, val] of Object.entries(profileNewData)) {
      if (typeof val !== 'object' || val === null) {
        console.log(`  ${key}:`, val)
      }
    }
  }

  // 5. FULL JSON DUMP for reference
  console.log('\n\n========== FULL DATA DUMP (for mapping) ==========\n')
  console.log('Writing full dump to scripts/r010_audit.json...')

  const fs = await import('fs')
  fs.writeFileSync('scripts/r010_audit.json', JSON.stringify({
    trade_imports: tradeData,
    portfolio_imports: portfolioData,
    behavioral_profiles: profileData,
    uploads: uploadsData,
    analysis_results: analysisRows,
    profiles_new: profileNewData,
  }, null, 2))

  console.log('Done. Check scripts/r010_audit.json for full data.')
}

audit().catch(console.error)
