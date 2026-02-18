-- Allow anonymous read access on trade_imports for public profile pages
CREATE POLICY "Allow public read on trade_imports" ON trade_imports
    FOR SELECT TO anon USING (true);

-- Allow anonymous read access on traders for profile context
CREATE POLICY "Allow public read on traders" ON traders
    FOR SELECT TO anon USING (true);
