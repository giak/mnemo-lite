-- db/init/02-partman-config.sql
-- Configure pg_partman for the events table using create_parent

-- Create the partitioning configuration and initial partitions for public.events
-- This function handles inserting into partman.part_config and creating partitions.
SELECT partman.create_parent(
    p_parent_table := 'public.events',       -- Parent table name (schema-qualified)
    p_control := 'timestamp',                -- Control column (partitioning key)
    p_type := 'range',                     -- Partitioning strategy (range for time)
    p_interval := '1 month',               -- Partition interval (correct syntax)
    p_premake := 4,                          -- Create 4 future partitions ahead of time
    p_start_partition := (now() - interval '1 month')::text -- Optional: Start partitioning from last month
    -- Add other parameters like p_template_table, p_jobmon etc. if needed
);

-- Note: Periodic maintenance still needs to be scheduled separately (e.g., via pg_cron)
-- using partman.run_maintenance_proc() or similar. 