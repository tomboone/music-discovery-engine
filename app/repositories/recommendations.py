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
        sql = text("""
            WITH seed AS (
                SELECT a.id
                FROM musicbrainz.artist a
                WHERE CAST(a.gid AS text) = :seed_mbid
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
                    collab.name AS collaborator_name,
                    (SELECT COUNT(DISTINCT acn3.artist)
                     FROM musicbrainz.l_artist_recording lar3
                     JOIN musicbrainz.link l3 ON l3.id = lar3.link
                     JOIN musicbrainz.link_type lt3 ON lt3.id = l3.link_type
                     JOIN musicbrainz.recording r3 ON r3.id = lar3.entity1
                     JOIN musicbrainz.artist_credit_name acn3
                         ON acn3.artist_credit = r3.artist_credit
                     WHERE lar3.entity0 = c.collaborator_id
                       AND lt3.name = c.rel_type
                    ) AS collaborator_artist_count
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
                  AND CAST(a.gid AS text) != :seed_mbid
            )
            ,
            paths_per_type AS (
                SELECT DISTINCT ON (artist_mbid, rel_type)
                    artist_mbid,
                    artist_name,
                    rel_type,
                    collaborator_name,
                    collaborator_artist_count
                FROM discovered
                ORDER BY artist_mbid, rel_type, collaborator_artist_count DESC
            )
            SELECT
                p.artist_mbid,
                p.artist_name,
                COUNT(DISTINCT p.rel_type) AS path_count,
                json_agg(
                    jsonb_build_object(
                        'relationship_type', p.rel_type,
                        'via', p.collaborator_name,
                        'collaborator_artist_count', p.collaborator_artist_count
                    )
                ) AS paths
            FROM paths_per_type p
            GROUP BY p.artist_mbid, p.artist_name
            HAVING COUNT(DISTINCT p.rel_type) >= :min_paths
            ORDER BY path_count DESC
            LIMIT :limit
        """)

        rows = session.execute(
            sql,
            {
                "seed_mbid": str(seed_mbid),
                "relationship_types": relationship_types,
                "min_paths": min_paths,
                "limit": limit,
            },
        ).fetchall()

        results = []
        for row in rows:
            paths = row.paths if isinstance(row.paths, list) else []
            for p in paths:
                if "collaborator_artist_count" in p:
                    p["collaborator_artist_count"] = int(p["collaborator_artist_count"])
            results.append(
                {
                    "artist_name": row.artist_name,
                    "artist_mbid": row.artist_mbid,
                    "path_count": row.path_count,
                    "paths": paths,
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
                "FROM musicbrainz.artist WHERE CAST(gid AS text) = :mbid"
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
                        WHEN CAST(a1.gid AS text) = :seed_mbid
                            THEN CAST(a2.gid AS text)
                        ELSE CAST(a1.gid AS text)
                    END AS related_mbid
                FROM musicbrainz.l_artist_artist laa
                JOIN musicbrainz.link l ON l.id = laa.link
                JOIN musicbrainz.link_type lt ON lt.id = l.link_type
                JOIN musicbrainz.artist a1 ON a1.id = laa.entity0
                JOIN musicbrainz.artist a2 ON a2.id = laa.entity1
                WHERE (CAST(a1.gid AS text) = :seed_mbid
                    OR CAST(a2.gid AS text) = :seed_mbid)
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
                WHERE CAST(a.gid AS text) = ANY(:mbids)
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
