import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session


class RecommendationRepository:
    def find_multi_path_artists(
        self,
        session: Session,
        seed_mbid: uuid.UUID,
        relationship_types: list[str],
        min_paths: int,
        limit: int,
    ) -> list[dict]:
        dialect = session.bind.dialect.name if session.bind else "postgresql"

        if dialect == "sqlite":
            return self._find_multi_path_sqlite(
                session, seed_mbid, relationship_types, min_paths, limit
            )
        else:
            return self._find_multi_path_postgres(
                session, seed_mbid, relationship_types, min_paths, limit
            )

    def _find_multi_path_sqlite(
        self,
        session: Session,
        seed_mbid: uuid.UUID,
        relationship_types: list[str],
        min_paths: int,
        limit: int,
    ) -> list[dict]:
        # Pad relationship types to 4 slots
        padded = list(relationship_types) + [""] * (4 - len(relationship_types))
        padded = padded[:4]

        sql = text("""
            WITH seed AS (
                SELECT a.id
                FROM musicbrainz.artist a
                WHERE a.gid = :seed_mbid
            ),
            seed_recordings AS (
                SELECT r.id AS recording_id
                FROM musicbrainz.recording r
                JOIN musicbrainz.artist_credit_name acn
                    ON acn.artist_credit = r.artist_credit
                JOIN seed ON seed.id = acn.artist
            ),
            collaborators AS (
                SELECT DISTINCT
                    lar.entity0 AS collaborator_id,
                    lt.name AS rel_type
                FROM musicbrainz.l_artist_recording lar
                JOIN musicbrainz.link l ON l.id = lar.link
                JOIN musicbrainz.link_type lt ON lt.id = l.link_type
                JOIN seed_recordings sr ON sr.recording_id = lar.entity1
                WHERE lt.name IN (:rt0, :rt1, :rt2, :rt3)
                  AND lar.entity0 NOT IN (SELECT id FROM seed)
            ),
            discovered AS (
                SELECT DISTINCT
                    a.gid AS artist_mbid,
                    a.name AS artist_name,
                    c.rel_type,
                    c.collaborator_id
                FROM collaborators c
                JOIN musicbrainz.l_artist_recording lar
                    ON lar.entity0 = c.collaborator_id
                JOIN musicbrainz.link l ON l.id = lar.link
                JOIN musicbrainz.link_type lt ON lt.id = l.link_type
                JOIN musicbrainz.recording r ON r.id = lar.entity1
                JOIN musicbrainz.artist_credit_name acn
                    ON acn.artist_credit = r.artist_credit
                JOIN musicbrainz.artist a ON a.id = acn.artist
                WHERE lt.name = c.rel_type
                  AND a.gid != :seed_mbid
                  AND a.id != c.collaborator_id
            )
            SELECT
                artist_mbid,
                artist_name,
                COUNT(DISTINCT rel_type) AS path_count,
                GROUP_CONCAT(DISTINCT rel_type || '::' || collaborator_id) AS paths_raw
            FROM discovered
            GROUP BY artist_mbid, artist_name
            HAVING COUNT(DISTINCT rel_type) >= :min_paths
            ORDER BY path_count DESC
            LIMIT :limit
        """)

        rows = session.execute(
            sql,
            {
                "seed_mbid": str(seed_mbid),
                "rt0": padded[0],
                "rt1": padded[1],
                "rt2": padded[2],
                "rt3": padded[3],
                "min_paths": min_paths,
                "limit": limit,
            },
        ).fetchall()

        results = []
        for row in rows:
            paths_raw = row.paths_raw or ""
            paths = []
            seen = set()
            for entry in paths_raw.split(","):
                if "::" in entry:
                    rel_type, collab_id = entry.split("::", 1)
                    if rel_type not in seen:
                        seen.add(rel_type)
                        # Look up collaborator name
                        collab_row = session.execute(
                            text("SELECT name FROM musicbrainz.artist WHERE id = :cid"),
                            {"cid": int(collab_id)},
                        ).fetchone()
                        via_name = collab_row.name if collab_row else str(collab_id)
                        count_row = session.execute(
                            text("""
                                SELECT COUNT(DISTINCT acn.artist) AS cnt
                                FROM musicbrainz.l_artist_recording lar
                                JOIN musicbrainz.link l ON l.id = lar.link
                                JOIN musicbrainz.link_type lt ON lt.id = l.link_type
                                JOIN musicbrainz.recording r ON r.id = lar.entity1
                                JOIN musicbrainz.artist_credit_name acn
                                    ON acn.artist_credit = r.artist_credit
                                WHERE lar.entity0 = :cid AND lt.name = :rtype
                            """),
                            {"cid": int(collab_id), "rtype": rel_type},
                        ).fetchone()
                        artist_count = count_row.cnt if count_row else 1
                        paths.append(
                            {
                                "relationship_type": rel_type,
                                "via": via_name,
                                "collaborator_artist_count": artist_count,
                            }
                        )

            results.append(
                {
                    "artist_name": row.artist_name,
                    "artist_mbid": row.artist_mbid,
                    "path_count": row.path_count,
                    "paths": paths,
                }
            )
        return results

    def _find_multi_path_postgres(
        self,
        session: Session,
        seed_mbid: uuid.UUID,
        relationship_types: list[str],
        min_paths: int,
        limit: int,
    ) -> list[dict]:
        # Main query — find multi-path artists WITHOUT the expensive
        # collaborator_artist_count subquery
        main_sql = text("""
            WITH seed AS (
                SELECT a.id
                FROM musicbrainz.artist a
                WHERE a.gid = CAST(:seed_mbid AS uuid)
            ),
            seed_recordings AS (
                SELECT r.id AS recording_id
                FROM musicbrainz.recording r
                JOIN musicbrainz.artist_credit_name acn
                    ON acn.artist_credit = r.artist_credit
                JOIN seed ON seed.id = acn.artist
            ),
            collaborators AS (
                SELECT DISTINCT
                    lar.entity0 AS collaborator_id,
                    lt.name AS rel_type
                FROM musicbrainz.l_artist_recording lar
                JOIN musicbrainz.link l ON l.id = lar.link
                JOIN musicbrainz.link_type lt ON lt.id = l.link_type
                JOIN seed_recordings sr ON sr.recording_id = lar.entity1
                WHERE lt.name = ANY(:relationship_types)
                  AND lar.entity0 NOT IN (SELECT id FROM seed)
            ),
            discovered AS (
                SELECT DISTINCT
                    CAST(a.gid AS text) AS artist_mbid,
                    a.name AS artist_name,
                    c.rel_type,
                    c.collaborator_id,
                    collab.name AS collaborator_name
                FROM collaborators c
                JOIN musicbrainz.l_artist_recording lar
                    ON lar.entity0 = c.collaborator_id
                JOIN musicbrainz.link l ON l.id = lar.link
                JOIN musicbrainz.link_type lt ON lt.id = l.link_type
                JOIN musicbrainz.recording r ON r.id = lar.entity1
                JOIN musicbrainz.artist_credit_name acn
                    ON acn.artist_credit = r.artist_credit
                JOIN musicbrainz.artist a ON a.id = acn.artist
                JOIN musicbrainz.artist collab ON collab.id = c.collaborator_id
                WHERE lt.name = c.rel_type
                  AND a.gid != CAST(:seed_mbid AS uuid)
                  AND a.id != c.collaborator_id
            ),
            paths_per_type AS (
                SELECT DISTINCT ON (artist_mbid, rel_type)
                    artist_mbid,
                    artist_name,
                    rel_type,
                    collaborator_name,
                    collaborator_id
                FROM discovered
            )
            SELECT
                p.artist_mbid,
                p.artist_name,
                COUNT(DISTINCT p.rel_type) AS path_count,
                json_agg(
                    jsonb_build_object(
                        'relationship_type', p.rel_type,
                        'via', p.collaborator_name,
                        'collaborator_id', p.collaborator_id
                    )
                ) AS paths
            FROM paths_per_type p
            GROUP BY p.artist_mbid, p.artist_name
            HAVING COUNT(DISTINCT p.rel_type) >= :min_paths
            ORDER BY path_count DESC
            LIMIT :limit
        """)

        rows = session.execute(
            main_sql,
            {
                "seed_mbid": str(seed_mbid),
                "relationship_types": relationship_types,
                "min_paths": min_paths,
                "limit": limit,
            },
        ).fetchall()

        # Collect unique collaborator IDs + rel_types for batch diversity lookup
        collab_keys: set[tuple[int, str]] = set()
        for row in rows:
            paths = row.paths if isinstance(row.paths, list) else []
            for p in paths:
                collab_keys.add((int(p["collaborator_id"]), p["relationship_type"]))

        # Batch query for collaborator_artist_count
        collab_counts: dict[tuple[int, str], int] = {}
        if collab_keys:
            collab_ids = list({k[0] for k in collab_keys})
            count_sql = text("""
                SELECT lar.entity0 AS collab_id,
                       lt.name AS rel_type,
                       COUNT(DISTINCT acn.artist) AS artist_count
                FROM musicbrainz.l_artist_recording lar
                JOIN musicbrainz.link l ON l.id = lar.link
                JOIN musicbrainz.link_type lt ON lt.id = l.link_type
                JOIN musicbrainz.recording r ON r.id = lar.entity1
                JOIN musicbrainz.artist_credit_name acn
                    ON acn.artist_credit = r.artist_credit
                WHERE lar.entity0 = ANY(:collab_ids)
                  AND lt.name = ANY(:rel_types)
                GROUP BY lar.entity0, lt.name
            """)
            rel_types_for_count = list({k[1] for k in collab_keys})
            count_rows = session.execute(
                count_sql,
                {"collab_ids": collab_ids, "rel_types": rel_types_for_count},
            ).fetchall()
            for cr in count_rows:
                collab_counts[(int(cr[0]), cr[1])] = int(cr[2])

        # Build results with collaborator_artist_count
        results = []
        for row in rows:
            paths = row.paths if isinstance(row.paths, list) else []
            clean_paths = []
            for p in paths:
                cid = int(p["collaborator_id"])
                rtype = p["relationship_type"]
                clean_paths.append(
                    {
                        "relationship_type": rtype,
                        "via": p["via"],
                        "collaborator_artist_count": collab_counts.get((cid, rtype), 1),
                    }
                )
            results.append(
                {
                    "artist_name": row.artist_name,
                    "artist_mbid": row.artist_mbid,
                    "path_count": row.path_count,
                    "paths": clean_paths,
                }
            )
        return results

    def get_artist_by_mbid(self, session: Session, mbid: uuid.UUID) -> dict | None:
        dialect = session.bind.dialect.name if session.bind else "postgresql"

        if dialect == "sqlite":
            sql = text("SELECT gid, name FROM musicbrainz.artist WHERE gid = :mbid")
        else:
            sql = text(
                "SELECT CAST(gid AS text) AS gid, name "
                "FROM musicbrainz.artist WHERE gid = CAST(:mbid AS uuid)"
            )

        row = session.execute(sql, {"mbid": str(mbid)}).fetchone()
        if row is None:
            return None
        return {"name": row.name, "mbid": row.gid}

    OBVIOUS_RELATIONSHIP_TYPES = [
        "member of band",
        "is person",
        "subgroup",
        "founder",
    ]

    def get_obvious_related_mbids(
        self, session: Session, seed_mbid: uuid.UUID
    ) -> set[str]:
        """Return MBIDs of artists obviously related to the seed (band members,
        alter egos, subgroups, founders). These should be excluded from
        recommendations since fans of the seed will already know them."""
        dialect = session.bind.dialect.name if session.bind else "postgresql"

        if dialect == "sqlite":
            placeholders = ", ".join(
                f":rt{i}" for i in range(len(self.OBVIOUS_RELATIONSHIP_TYPES))
            )
            sql = text(f"""
                SELECT DISTINCT
                    CASE
                        WHEN a1.gid = :seed_mbid THEN a2.gid
                        ELSE a1.gid
                    END AS related_mbid
                FROM musicbrainz.l_artist_artist laa
                JOIN musicbrainz.link l ON l.id = laa.link
                JOIN musicbrainz.link_type lt ON lt.id = l.link_type
                JOIN musicbrainz.artist a1 ON a1.id = laa.entity0
                JOIN musicbrainz.artist a2 ON a2.id = laa.entity1
                WHERE (a1.gid = :seed_mbid OR a2.gid = :seed_mbid)
                  AND lt.name IN ({placeholders})
            """)
            params: dict = {
                "seed_mbid": str(seed_mbid),
                **{
                    f"rt{i}": rt for i, rt in enumerate(self.OBVIOUS_RELATIONSHIP_TYPES)
                },
            }
        else:
            sql = text("""
                SELECT DISTINCT
                    CASE
                        WHEN a1.gid = CAST(:seed_mbid AS uuid)
                            THEN CAST(a2.gid AS text)
                        ELSE CAST(a1.gid AS text)
                    END AS related_mbid
                FROM musicbrainz.l_artist_artist laa
                JOIN musicbrainz.link l ON l.id = laa.link
                JOIN musicbrainz.link_type lt ON lt.id = l.link_type
                JOIN musicbrainz.artist a1 ON a1.id = laa.entity0
                JOIN musicbrainz.artist a2 ON a2.id = laa.entity1
                WHERE (a1.gid = CAST(:seed_mbid AS uuid)
                    OR a2.gid = CAST(:seed_mbid AS uuid))
                  AND lt.name = ANY(:rel_types)
            """)
            params = {
                "seed_mbid": str(seed_mbid),
                "rel_types": self.OBVIOUS_RELATIONSHIP_TYPES,
            }

        rows = session.execute(sql, params).fetchall()
        return {str(row[0]) for row in rows}

    def get_artist_tags(
        self, session: Session, artist_mbids: list[str]
    ) -> dict[str, dict[str, int]]:
        if not artist_mbids:
            return {}
        dialect = session.bind.dialect.name if session.bind else "postgresql"

        if dialect == "sqlite":
            placeholders = ", ".join(f":m{i}" for i in range(len(artist_mbids)))
            sql = text(f"""
                SELECT a.gid AS artist_mbid, t.name AS tag_name, at.count
                FROM musicbrainz.artist a
                JOIN musicbrainz.artist_tag at ON at.artist = a.id
                JOIN musicbrainz.tag t ON t.id = at.tag
                WHERE a.gid IN ({placeholders})
                  AND at.count > 0
            """)
            params = {f"m{i}": mbid for i, mbid in enumerate(artist_mbids)}
        else:
            sql = text("""
                SELECT CAST(a.gid AS text) AS artist_mbid,
                       t.name AS tag_name, at.count
                FROM musicbrainz.artist a
                JOIN musicbrainz.artist_tag at ON at.artist = a.id
                JOIN musicbrainz.tag t ON t.id = at.tag
                WHERE a.gid = ANY(CAST(:mbids AS uuid[]))
                  AND at.count > 0
            """)
            params = {"mbids": artist_mbids}

        rows = session.execute(sql, params).fetchall()
        result: dict[str, dict[str, int]] = {}
        for row in rows:
            mbid = row[0]
            tag_name = row[1]
            tag_count = int(row[2])
            if mbid not in result:
                result[mbid] = {}
            result[mbid][tag_name] = tag_count
        return result
