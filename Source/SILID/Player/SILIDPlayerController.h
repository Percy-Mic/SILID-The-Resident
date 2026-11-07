// Player controller: builds its Enhanced Input mapping in code so the
// project compiles and runs without any imported input assets (designers can
// later remap through the standard Enhanced Input editor flow).

#pragma once

#include "GameFramework/PlayerController.h"
#include "SILIDPlayerController.generated.h"

class UInputMappingContext;
class UInputAction;
class USILIDHUDWidget;
class ASILIDOpeningCar;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnExamineRequested, const FText&, Text);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnPromptChanged, const FText&, Prompt);

UCLASS()
class SILID_API ASILIDPlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	ASILIDPlayerController();

	/** The player character for this controller. */
	class ASILIDCharacter* GetSILIDCharacter() const;

	// ---- UI hooks ----
	UPROPERTY(BlueprintAssignable, Category = "SILID|UI")
	FOnExamineRequested OnExamineRequested;

	UPROPERTY(BlueprintAssignable, Category = "SILID|UI")
	FOnPromptChanged OnPromptChanged;

	/** Push examine text into the UI (called by the character). */
	void ShowExamineText(const FText& Text);

	/** Push prompt text into the UI (called by the HUD poller and by the
	 * Act I opening car's message delegate). UFUNCTION so dynamic delegates
	 * can bind to it — the opening car's cues arrive through here. */
	UFUNCTION(BlueprintCallable, Category = "SILID|UI")
	void SetPromptText(const FText& Text);

	/** Sensitivity scaling (spec section 25). */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input", meta = (ClampMin = "0.1", ClampMax = "4"))
	float MouseSensitivity = 1.f;

	/** Bound by the game mode at BeginPlay (WBP subclass of USILIDHUDWidget). */
	UPROPERTY(BlueprintReadOnly, Category = "SILID|UI")
	TObjectPtr<USILIDHUDWidget> HUDWidget;

	/** The Act I opening car while its drive is live (null in the mansion).
	 * While set and driving, HandleMove routes WASD to the car instead of the
	 * character, and E beside the wreck runs the roadside checks. */
	UPROPERTY(Transient)
	TObjectPtr<ASILIDOpeningCar> ActiveOpeningCar;

protected:
	virtual void OnPossess(APawn* InPawn) override;
	virtual void SetupInputComponent() override;
	virtual void OnUnPossess() override;

private:
	// Enhanced Input assets built in code (paths under /Engine or generated)
	UPROPERTY()
	TObjectPtr<UInputMappingContext> DefaultContext;

	UPROPERTY()
	TObjectPtr<UInputAction> IA_Move;      // Vector2D WASD
	UPROPERTY()
	TObjectPtr<UInputAction> IA_Look;      // Axis2D mouse
	UPROPERTY()
	TObjectPtr<UInputAction> IA_Run;       // hold Shift
	UPROPERTY()
	TObjectPtr<UInputAction> IA_Sprint;    // hold Ctrl
	UPROPERTY()
	TObjectPtr<UInputAction> IA_Crouch;    // tap C
	UPROPERTY()
	TObjectPtr<UInputAction> IA_Interact;  // tap E
	UPROPERTY()
	TObjectPtr<UInputAction> IA_Examine;   // hold Q
	UPROPERTY()
	TObjectPtr<UInputAction> IA_Flashlight;// tap F
	UPROPERTY()
	TObjectPtr<UInputAction> IA_UseItem;   // tap LMB (use held on focus)
	UPROPERTY()
	TObjectPtr<UInputAction> IA_Drop;      // tap G
	UPROPERTY()
	TObjectPtr<UInputAction> IA_Throw;     // tap RMB (throw held)
	UPROPERTY()
	TObjectPtr<UInputAction> IA_Journal;   // tap Tab

	void BuildInputAssets();

	// bound handlers
	void HandleMove(const struct FInputActionValue& Value);
	void HandleLook(const struct FInputActionValue& Value);
	void HandleRun(const struct FInputActionValue& Value);
	void HandleSprint(const struct FInputActionValue& Value);
	void HandleCrouch();
	void HandleInteract();
	void HandleExamine(const struct FInputActionValue& Value);
	void HandleFlashlight();
	void HandleUseItem();
	void HandleDrop();
	void HandleThrow();
	void HandleJournal();

	FTimerHandle PromptPollTimer;
};
