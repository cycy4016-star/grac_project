import chromadb
c = chromadb.PersistentClient("C:\\Users\\techw\\Downloads\\grac_project\\grac_project\\data\\vectorstore")
cols = c.list_collections()
if cols:
    for col in cols:
        print(f"  {col.name}: {col.count()} chunks")
else:
    print("  No collections found")
