# Backup

If running under Windows inside default Docker, backup with:
```powershell
docker run --rm -v fireflyiii_firefly_iii_db:/tmp -v "$HOME\backups\firefly:/backup" ubuntu tar -czvf /backup/firefly_db.tar -C /tmp .
```

Restore with:
```powershell
docker run --rm -v fireflyiii_firefly_iii_db:/recover -v "$HOME\backups\firefly:/backup" ubuntu tar -xvf /backup/firefly_db.tar -C /recover --strip 1
```
