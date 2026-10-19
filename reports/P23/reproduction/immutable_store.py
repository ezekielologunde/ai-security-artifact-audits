"""Narrow insert-only overlay for the pinned in-memory reference store."""
from ragtrap.datastore import ProvenanceDatastore
from ragtrap.hashing import sha256_text
class ImmutableIdStore(ProvenanceDatastore):
    def put(self,chunk,record):
        if chunk.chunk_id in self.records or chunk.chunk_id in self.chunks:
            raise ValueError('Chunk ID already exists; use a new versioned identity')
        if chunk.chunk_id!=record.chunk_id or chunk.principal!=record.principal or chunk.source_uri!=record.source_uri:
            raise ValueError('Chunk and record identities differ')
        if record.granularity!='chunk' or sha256_text(chunk.text)!=record.content_hash:
            raise ValueError('A matching per-chunk content hash is required')
        super().put(chunk,record)

class IndexConsistentUpsertStore(ProvenanceDatastore):
    """Single-threaded upsert alternative; caller ownership authorization is external."""
    def put(self,chunk,record):
        if record.principal in self.revoked_principals:
            raise ValueError('Source is revoked')
        if chunk.chunk_id!=record.chunk_id or chunk.principal!=record.principal or chunk.source_uri!=record.source_uri:
            raise ValueError('Chunk and record identities differ')
        if record.granularity!='chunk' or sha256_text(chunk.text)!=record.content_hash:
            raise ValueError('A matching per-chunk content hash is required')
        if chunk.chunk_id in self.records:self.remove_chunk(chunk.chunk_id)
        super().put(chunk,record)
