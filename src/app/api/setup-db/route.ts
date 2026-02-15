import { supabase } from "@/lib/supabase";
import { NextResponse } from "next/server";
import { readFileSync } from "fs";
import { join } from "path";

export async function POST() {
  try {
    // Read schema SQL from file
    const schemaPath = join(process.cwd(), "src/lib/schema.sql");
    const sql = readFileSync(schemaPath, "utf-8");

    // Execute each statement separately
    const statements = sql
      .split(";")
      .map((s) => s.trim())
      .filter((s) => s.length > 0 && !s.startsWith("--"));

    const errors: string[] = [];

    for (const statement of statements) {
      const { error } = await supabase.rpc("exec_sql", {
        sql: statement + ";",
      });
      if (error) {
        errors.push(error.message);
      }
    }

    if (errors.length > 0) {
      return NextResponse.json(
        {
          message:
            "Some statements failed. Run schema.sql directly in Supabase SQL Editor for best results.",
          errors,
        },
        { status: 207 },
      );
    }

    return NextResponse.json({ success: true });
  } catch (err) {
    return NextResponse.json(
      {
        error: "Failed to execute schema. Run src/lib/schema.sql directly in Supabase SQL Editor.",
      },
      { status: 500 },
    );
  }
}
