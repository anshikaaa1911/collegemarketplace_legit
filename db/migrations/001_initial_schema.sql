CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TYPE data_origin AS ENUM ('synthetic', 'real');
CREATE TYPE account_status AS ENUM ('pending', 'active', 'suspended', 'disabled');
CREATE TYPE item_category AS ENUM ('clothes', 'books', 'stationery', 'toys', 'utensils', 'blankets', 'electronics', 'other');
CREATE TYPE age_group AS ENUM ('infant', 'child', 'teen', 'adult', 'all_ages', 'unspecified');
CREATE TYPE item_status AS ENUM ('draft', 'submitted', 'needs_review', 'approved', 'rejected', 'reserved', 'donated', 'archived');
CREATE TYPE need_status AS ENUM ('open', 'paused', 'fulfilled', 'expired', 'cancelled');
CREATE TYPE model_stage AS ENUM ('baseline', 'regression', 'ranker');
CREATE TYPE match_status AS ENUM ('suggested', 'accepted', 'rejected', 'pickup_scheduled', 'in_transit', 'delivered', 'confirmed');
CREATE TYPE pickup_status AS ENUM ('claimed', 'scheduled', 'picked_up', 'cancelled');
CREATE TYPE delivery_status AS ENUM ('in_transit', 'delivered', 'confirmed', 'failed');
CREATE TYPE feedback_label AS ENUM ('accepted', 'rejected', 'fulfilled');
CREATE TYPE notification_channel AS ENUM ('email', 'whatsapp', 'sms');
CREATE TYPE notification_status AS ENUM ('queued', 'sent', 'delivered', 'failed');

CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_subject text NOT NULL UNIQUE,
    email text NOT NULL,
    phone text,
    display_name text NOT NULL,
    account_status account_status NOT NULL DEFAULT 'pending',
    recipient_verified_at timestamptz,
    data_origin data_origin NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX users_email_lower_uq ON users (lower(email));
CREATE UNIQUE INDEX users_id_origin_uq ON users (id, data_origin);

CREATE TABLE roles (
    id smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_key text NOT NULL UNIQUE CHECK (role_key IN ('donor', 'coordinator', 'volunteer', 'admin')),
    name text NOT NULL
);
INSERT INTO roles (role_key, name) VALUES
    ('donor', 'Donor'),
    ('coordinator', 'Village Coordinator'),
    ('volunteer', 'Volunteer'),
    ('admin', 'College Admin');

CREATE TABLE user_roles (
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id smallint NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    granted_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE villages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    district text NOT NULL,
    state text NOT NULL DEFAULT 'Himachal Pradesh',
    location geography(Point, 4326),
    data_origin data_origin NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (name, district, state)
);
CREATE INDEX villages_location_gix ON villages USING gist (location);
CREATE UNIQUE INDEX villages_id_origin_uq ON villages (id, data_origin);

CREATE TABLE village_coordinators (
    village_id uuid NOT NULL,
    user_id uuid NOT NULL,
    data_origin data_origin NOT NULL,
    assigned_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (village_id, user_id),
    FOREIGN KEY (village_id, data_origin) REFERENCES villages(id, data_origin) ON DELETE CASCADE,
    FOREIGN KEY (user_id, data_origin) REFERENCES users(id, data_origin) ON DELETE RESTRICT
);

CREATE TABLE items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    donor_id uuid NOT NULL,
    category item_category NOT NULL,
    quantity integer NOT NULL DEFAULT 1 CHECK (quantity > 0),
    title text NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 160),
    description text,
    age_group age_group NOT NULL DEFAULT 'unspecified',
    condition_score smallint CHECK (condition_score BETWEEN 1 AND 10),
    item_status item_status NOT NULL DEFAULT 'submitted',
    data_origin data_origin NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (donor_id, data_origin) REFERENCES users(id, data_origin) ON DELETE RESTRICT
);
CREATE INDEX items_matching_idx ON items (category, item_status, data_origin);
CREATE INDEX items_donor_created_idx ON items (donor_id, created_at DESC);
CREATE UNIQUE INDEX items_id_origin_uq ON items (id, data_origin);

CREATE TABLE item_pickup_details (
    item_id uuid PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
    address_text text NOT NULL,
    location geography(Point, 4326),
    access_instructions text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX item_pickup_location_gix ON item_pickup_details USING gist (location);

CREATE TABLE item_images (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id uuid NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    storage_key text NOT NULL UNIQUE,
    mime_type text NOT NULL CHECK (mime_type IN ('image/jpeg', 'image/png', 'image/webp')),
    size_bytes integer NOT NULL CHECK (size_bytes BETWEEN 1 AND 10485760),
    sort_order smallint NOT NULL CHECK (sort_order BETWEEN 1 AND 4),
    sha256 char(64),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (item_id, sort_order)
);

CREATE TABLE needs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    village_id uuid NOT NULL,
    created_by uuid NOT NULL,
    category item_category NOT NULL,
    quantity integer NOT NULL CHECK (quantity > 0),
    age_group age_group NOT NULL DEFAULT 'unspecified',
    urgency smallint NOT NULL CHECK (urgency BETWEEN 1 AND 5),
    deadline date,
    notes text,
    input_language text CHECK (input_language IS NULL OR input_language IN ('hi', 'en', 'mixed', 'other')),
    need_status need_status NOT NULL DEFAULT 'open',
    data_origin data_origin NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (village_id, data_origin) REFERENCES villages(id, data_origin) ON DELETE RESTRICT,
    FOREIGN KEY (created_by, data_origin) REFERENCES users(id, data_origin) ON DELETE RESTRICT
);
CREATE INDEX needs_matching_idx ON needs (category, need_status, data_origin, urgency DESC);
CREATE INDEX needs_village_created_idx ON needs (village_id, created_at DESC);
CREATE UNIQUE INDEX needs_id_origin_uq ON needs (id, data_origin);

CREATE TABLE recommendation_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    model_stage model_stage NOT NULL,
    model_name text NOT NULL,
    model_version text NOT NULL,
    data_origin data_origin NOT NULL,
    parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
    candidate_count integer NOT NULL DEFAULT 0 CHECK (candidate_count >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX recommendation_runs_id_origin_uq ON recommendation_runs (id, data_origin);

CREATE TABLE matches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_run_id uuid NOT NULL,
    item_id uuid NOT NULL,
    need_id uuid NOT NULL,
    score numeric(6, 5) NOT NULL CHECK (score BETWEEN 0 AND 1),
    rank_position integer NOT NULL CHECK (rank_position > 0),
    feature_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    reason text,
    match_status match_status NOT NULL DEFAULT 'suggested',
    accepted_by uuid REFERENCES users(id) ON DELETE RESTRICT,
    rejection_reason text,
    accepted_at timestamptz,
    rejected_at timestamptz,
    data_origin data_origin NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (recommendation_run_id, data_origin) REFERENCES recommendation_runs(id, data_origin) ON DELETE RESTRICT,
    FOREIGN KEY (item_id, data_origin) REFERENCES items(id, data_origin) ON DELETE RESTRICT,
    FOREIGN KEY (need_id, data_origin) REFERENCES needs(id, data_origin) ON DELETE RESTRICT,
    UNIQUE (recommendation_run_id, item_id, need_id),
    CHECK (match_status <> 'rejected' OR length(trim(coalesce(rejection_reason, ''))) > 0)
);
CREATE INDEX matches_need_rank_idx ON matches (need_id, rank_position);
CREATE INDEX matches_status_created_idx ON matches (match_status, created_at DESC);
CREATE UNIQUE INDEX matches_id_origin_uq ON matches (id, data_origin);

CREATE TABLE pickups (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    volunteer_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    pickup_status pickup_status NOT NULL DEFAULT 'claimed',
    scheduled_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE pickup_items (
    pickup_id uuid NOT NULL REFERENCES pickups(id) ON DELETE CASCADE,
    item_id uuid NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
    added_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (pickup_id, item_id)
);

CREATE TABLE deliveries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id uuid NOT NULL UNIQUE REFERENCES matches(id) ON DELETE RESTRICT,
    pickup_id uuid REFERENCES pickups(id) ON DELETE RESTRICT,
    village_id uuid NOT NULL REFERENCES villages(id) ON DELETE RESTRICT,
    delivery_status delivery_status NOT NULL DEFAULT 'in_transit',
    delivered_at timestamptz,
    confirmed_at timestamptz,
    confirmed_by uuid REFERENCES users(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (delivery_status <> 'confirmed' OR (confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL))
);
CREATE INDEX deliveries_village_confirmed_idx ON deliveries (village_id, confirmed_at DESC);

CREATE TABLE donations_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    delivery_id uuid NOT NULL UNIQUE REFERENCES deliveries(id) ON DELETE RESTRICT,
    item_id uuid NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
    need_id uuid NOT NULL REFERENCES needs(id) ON DELETE RESTRICT,
    village_id uuid NOT NULL REFERENCES villages(id) ON DELETE RESTRICT,
    confirmed_at timestamptz NOT NULL,
    data_origin data_origin NOT NULL
);
CREATE INDEX donations_history_village_date_idx ON donations_history (village_id, confirmed_at);

CREATE TABLE feedback (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    label feedback_label NOT NULL,
    data_origin data_origin NOT NULL,
    reason_code text,
    comment text,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (match_id, data_origin) REFERENCES matches(id, data_origin) ON DELETE RESTRICT,
    FOREIGN KEY (actor_id, data_origin) REFERENCES users(id, data_origin) ON DELETE RESTRICT
);
CREATE INDEX feedback_match_created_idx ON feedback (match_id, created_at DESC);

CREATE TABLE notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel notification_channel NOT NULL,
    template_key text NOT NULL,
    delivery_status notification_status NOT NULL DEFAULT 'queued',
    provider_reference text,
    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz
);
CREATE INDEX notifications_user_created_idx ON notifications (user_id, created_at DESC);

CREATE TABLE events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id uuid,
    event_type text NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid,
    data_origin data_origin NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (actor_id, data_origin) REFERENCES users(id, data_origin) ON DELETE RESTRICT
);
CREATE INDEX events_entity_time_idx ON events (entity_type, entity_id, occurred_at);
CREATE INDEX events_type_time_idx ON events (event_type, occurred_at);

CREATE TABLE audit_log (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id uuid REFERENCES users(id) ON DELETE SET NULL,
    action text NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_log_entity_time_idx ON audit_log (entity_type, entity_id, occurred_at DESC);
