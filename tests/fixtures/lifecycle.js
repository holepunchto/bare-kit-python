Bare.on('suspend', () => Bare.IPC.write('suspend')).on('resume', () => Bare.IPC.write('resume'))

Bare.IPC.write('ready')
