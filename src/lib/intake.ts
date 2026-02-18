import { supabase } from './supabase'

const RAILWAY_API_URL =
  process.env.NEXT_PUBLIC_RAILWAY_API_URL || 'https://yabo-production.up.railway.app'

export interface IntakeFormData {
  name: string
  email: string
  phone: string
  brokerage: string
  referredBy: string
}

interface TraderRecord {
  id: string
  name: string
  email: string
}

/**
 * Submit the full intake form: create trader, upload files, trigger processing.
 *
 * Files are always saved to Supabase Storage first. Railway processing is
 * best-effort — if it fails, we can reprocess later from stored files.
 */
export async function submitIntake(
  formData: IntakeFormData,
  csvFile: File | null,
  screenshots: File[]
): Promise<{ success: boolean; error?: string }> {
  // Step 1: Create trader record
  let trader: TraderRecord
  try {
    const { data, error } = await supabase
      .from('traders')
      .insert({
        name: formData.name,
        email: formData.email,
        phone: formData.phone || null,
        brokerage: formData.brokerage,
        referred_by: formData.referredBy || null,
        status: 'pending',
        created_at: new Date().toISOString(),
      })
      .select()
      .single()

    if (error || !data) {
      console.error('Supabase trader insert failed:', error)
      return { success: false, error: 'Upload failed. Please try again.' }
    }
    trader = data as TraderRecord
  } catch {
    return { success: false, error: 'Upload failed. Please try again.' }
  }

  // Step 2: Upload files to Supabase Storage (parallel)
  const uploadPromises: Promise<void>[] = []

  if (csvFile) {
    const csvPath = `intake/${trader.id}/${csvFile.name}`
    uploadPromises.push(
      supabase.storage
        .from('trade-data')
        .upload(csvPath, csvFile)
        .then(({ error }) => {
          if (error) console.error('CSV storage upload failed:', error)
        })
    )
  }

  for (const screenshot of screenshots) {
    const ssPath = `intake/${trader.id}/screenshots/${screenshot.name}`
    uploadPromises.push(
      supabase.storage
        .from('trade-data')
        .upload(ssPath, screenshot)
        .then(({ error }) => {
          if (error) console.error('Screenshot storage upload failed:', error)
        })
    )
  }

  // Wait for all storage uploads
  await Promise.allSettled(uploadPromises)

  // Step 3: Send CSV to Railway for processing (best-effort)
  if (csvFile) {
    processCsvInBackground(trader, csvFile, formData.brokerage)
  }

  // Step 4: Send screenshots to Railway for extraction (best-effort)
  if (screenshots.length > 0) {
    processScreenshotsInBackground(trader, screenshots, formData.brokerage)
  }

  return { success: true }
}

/**
 * Fire-and-forget CSV processing. Saves result or error to trade_imports.
 */
async function processCsvInBackground(
  trader: TraderRecord,
  csvFile: File,
  brokerage: string
) {
  const formPayload = new FormData()
  formPayload.append('file', csvFile)

  try {
    const response = await fetch(`${RAILWAY_API_URL}/analyze`, {
      method: 'POST',
      body: formPayload,
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const profile = await response.json()

    await supabase.from('trade_imports').insert({
      trader_id: trader.id,
      source_type: 'csv',
      brokerage_detected:
        profile.extraction?.metadata?.csv_format || brokerage,
      raw_result: profile,
      status: 'processed',
      trade_count: profile.extraction?.metadata?.total_trades || 0,
      profile_id: profile.profile_id || null,
      created_at: new Date().toISOString(),
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error'
    await supabase.from('trade_imports').insert({
      trader_id: trader.id,
      source_type: 'csv',
      brokerage_detected: brokerage,
      status: 'failed',
      error: message,
      created_at: new Date().toISOString(),
    })
  }
}

/**
 * Fire-and-forget screenshot processing. Saves result or error to trade_imports.
 */
async function processScreenshotsInBackground(
  trader: TraderRecord,
  screenshots: File[],
  brokerage: string
) {
  const formPayload = new FormData()
  for (const screenshot of screenshots) {
    formPayload.append('files', screenshot)
  }

  try {
    const response = await fetch(`${RAILWAY_API_URL}/extract_screenshots`, {
      method: 'POST',
      body: formPayload,
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const extraction = await response.json()

    await supabase.from('trade_imports').insert({
      trader_id: trader.id,
      source_type: 'screenshots',
      brokerage_detected: extraction.brokerage_detected || brokerage,
      raw_result: extraction,
      status: 'processed',
      trade_count: extraction.trades?.length || 0,
      created_at: new Date().toISOString(),
    })

    // Convert extracted trades to CSV and run through /analyze for a full profile
    if (extraction.trades?.length) {
      await analyzeExtractedTrades(trader, extraction, brokerage)
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error'
    await supabase.from('trade_imports').insert({
      trader_id: trader.id,
      source_type: 'screenshots',
      status: 'failed',
      error: message,
      created_at: new Date().toISOString(),
    })
  }
}

const TICKER_NORMALIZATIONS: Record<string, string> = {
  APPLOVIN: 'APP',
}

async function analyzeExtractedTrades(
  trader: TraderRecord,
  extraction: { trades: Array<Record<string, unknown>>; brokerage_detected?: string },
  brokerage: string
) {
  const SKIP_SIDES = new Set(['INTEREST', 'DIVIDEND'])

  const filtered = extraction.trades.filter((t) => {
    if (!t.ticker) return false
    const side = String(t.side || '').toUpperCase()
    return !SKIP_SIDES.has(side)
  })

  if (filtered.length === 0) return

  const rows = filtered.map((t) => {
    let ticker = String(t.ticker)
    ticker = TICKER_NORMALIZATIONS[ticker.toUpperCase()] || ticker
    return [
      t.date || '',
      t.side || '',
      ticker,
      t.quantity ?? '',
      t.price ?? '',
      t.amount ?? t.total ?? '',
    ].join(',')
  })

  const csvString = ['Date,Action,Ticker,Quantity,Price,Amount', ...rows].join('\n')
  const blob = new Blob([csvString], { type: 'text/csv' })
  const csvFile = new File([blob], 'screenshot_trades.csv', { type: 'text/csv' })

  const formPayload = new FormData()
  formPayload.append('file', csvFile)

  try {
    const response = await fetch(`${RAILWAY_API_URL}/analyze`, {
      method: 'POST',
      body: formPayload,
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const profile = await response.json()

    await supabase.from('trade_imports').insert({
      trader_id: trader.id,
      source_type: 'screenshot_analyzed',
      brokerage_detected: extraction.brokerage_detected || brokerage,
      raw_result: profile,
      status: 'processed',
      trade_count: filtered.length,
      profile_id: profile.profile_id || null,
      created_at: new Date().toISOString(),
    })
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error'
    await supabase.from('trade_imports').insert({
      trader_id: trader.id,
      source_type: 'screenshot_analyzed',
      status: 'failed',
      error: message,
      created_at: new Date().toISOString(),
    })
  }
}
