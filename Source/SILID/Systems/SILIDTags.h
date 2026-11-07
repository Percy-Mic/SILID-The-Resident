// Native gameplay tag constants. Native registration happens before any
// gameplay object can read them, so no static FGameplayTag lookup is allowed.

#pragma once

#include "CoreMinimal.h"
#include "GameplayTagContainer.h"
#include "NativeGameplayTags.h"

namespace SILIDTags
{
	// noise classes (spec section 8)
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(NoiseFootstep);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(NoiseRun);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(NoiseDoor);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(NoiseImpact);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(NoiseBreak);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(NoiseDrawer);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(NoiseDevice);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(NoiseVoice);

	// item unlock families (spec section 6: keys)
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(LockFrontDoor);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(LockBackDoor);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(LockDrawer);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(LockSafe);

	// room ids (spec section 16)
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(RoomSala);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(RoomKusina);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(RoomAklat);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(RoomHallway);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(RoomKwarto);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(RoomBodega);

	// power nodes (doc 01 section 5 Power.Node.* - P8 electricity). Devices
	// name their circuit node with a tag; the electrical subsystem walks the
	// graph by tag, never by hard reference.
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(PowerNodeGenerator);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(PowerNodeFuseBox);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(PowerNodeBreaker);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(PowerNodeHouse);

	// story facts (P13 objective fabric - doc 09 section 9). System-grammar
	// tags, not story nouns; DA_Story owns the narrative wording.
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(StoryEscapeReady);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(StoryEscapeUsed);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(StoryMachineRepaired);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(StoryPowerRunning);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(StoryPowerOff);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(StoryPowerBreakerTripped);
	UE_DECLARE_GAMEPLAY_TAG_EXTERN(StoryPowerAnyNode);
}
