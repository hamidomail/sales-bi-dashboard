-- Staging: load raw CSVs with explicit types.
CREATE OR REPLACE TABLE stg_products AS
SELECT product_id, product_name, category, list_price::DECIMAL(10,2) AS list_price, unit_cost::DECIMAL(10,2) AS unit_cost
FROM read_csv_auto('{raw}/products.csv');

CREATE OR REPLACE TABLE stg_customers AS
SELECT customer_id, signup_date::DATE AS signup_date, acquisition_channel, country, region
FROM read_csv_auto('{raw}/customers.csv');

CREATE OR REPLACE TABLE stg_orders AS
SELECT order_id, customer_id, order_date::DATE AS order_date, order_number::INT AS order_number,
       discount_rate::DOUBLE AS discount_rate, device, shipping_fee::DECIMAL(10,2) AS shipping_fee
FROM read_csv_auto('{raw}/orders.csv');

CREATE OR REPLACE TABLE stg_order_lines AS
SELECT order_id, product_id, quantity::INT AS quantity, unit_price::DECIMAL(10,2) AS unit_price,
       unit_cost::DECIMAL(10,2) AS unit_cost, is_refunded::BOOLEAN AS is_refunded
FROM read_csv_auto('{raw}/order_lines.csv');

CREATE OR REPLACE TABLE stg_marketing_spend AS
SELECT date::DATE AS date, channel, spend::DECIMAL(12,2) AS spend, clicks::INT AS clicks, impressions::BIGINT AS impressions
FROM read_csv_auto('{raw}/marketing_spend.csv');
