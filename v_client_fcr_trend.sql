-- sql/views/v_client_fcr_trend.sql
CREATE OR REPLACE VIEW v_client_fcr_trend AS
SELECT
    client_id,
    DATE(interaction_timestamp) AS metric_date,
    CAST(SUM(CASE WHEN is_resolved_first_contact = true THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) AS metric_value
FROM fact_interactions
GROUP BY 1, 2;