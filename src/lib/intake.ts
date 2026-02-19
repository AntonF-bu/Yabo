import { supabase } from './supabase'

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_RAILWAY_API_URL ||
  'https://yabo-production.up.railway.app'

export interface IntakeFormData {
  name: string
  email: string
  phone: string
  brokerage: string
  referredBy: string
}

/**
 * Generate a human-readable profile_id like "DS847" from user's name.
 * First initial + last initial + 3 random digits.
 * Retries on collision.
 */
function generateProfileId(name: string): string {
  const parts = name.trim().split(/\s+/)
  const first = (parts[0]?.[0] || 'X').toUpperCase()
  const last = (parts.length > 1 ? parts[parts.length - 1][0] : parts[0]?.[1] || 'X').toUpperCase()
  const digits = String(Math.floor(Math.random() * 900) + 100)
  return `${first}${last}${digits}`
}

/**
 * Submit the intake form: create profile, upload files, trigger processing.
 *
 * New schema flow:
 * 1. Create row in profiles_new
 * 2. Upload each file to Supabase Storage (bucket: "uploads")
 * 3. Create row in uploads table per file
 * 4. Fire POST /process-upload to Railway for each upload_id
 * 5. Return profile_id for confirmation screen
 */
export async function submitIntake(
  formData: IntakeFormData,
  files: File[]
): Promise<{ success: boolean; error?: string; profileId?: string }> {
  // Step 1: Generate profile_id and create profile
  let profileId = generateProfileId(formData.name)

  // Retry up to 3 times on collision
  for (let attempt = 0; attempt < 3; attempt++) {
    const { error } = await supabase
      .from('profiles_new')
      .insert({
        profile_id: profileId,
        name: formData.name,
        email: formData.email,
        phone: formData.phone || null,
        brokerage: formData.brokerage,
      })

    if (!error) break

    if (error.code === '23505') {
      // Unique constraint violation — retry with new id
      profileId = generateProfileId(formData.name)
      continue
    }

    console.error('Supabase profile insert failed:', error)
    return { success: false, error: 'Upload failed. Please try again.' }
  }

  // Step 2 & 3: Upload each file to storage + create uploads row + trigger processing
  for (const file of files) {
    const filePath = `${profileId}/${file.name}`

    // Upload to Supabase Storage bucket "uploads"
    const { error: storageError } = await supabase.storage
      .from('uploads')
      .upload(filePath, file)

    if (storageError) {
      console.error('Storage upload failed:', storageError)
      continue
    }

    // Create uploads row
    const { data: uploadRow, error: uploadError } = await supabase
      .from('uploads')
      .insert({
        profile_id: profileId,
        file_path: filePath,
        file_name: file.name,
        file_size_bytes: file.size,
        status: 'uploaded',
      })
      .select('id')
      .single()

    if (uploadError || !uploadRow) {
      console.error('Upload row insert failed:', uploadError)
      continue
    }

    // Fire and forget: trigger Railway processing
    triggerProcessing(uploadRow.id)
  }

  return { success: true, profileId }
}

/**
 * Fire-and-forget: tell Railway to process an upload.
 */
function triggerProcessing(uploadId: string) {
  fetch(`${API_URL}/process-upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ upload_id: uploadId }),
  }).catch((err) => {
    console.error('[process-upload] Failed to trigger:', err)
  })
}
